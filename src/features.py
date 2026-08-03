"""
Carga de datos y construccion de variables para el modelo de direccion del
tipo de cambio USDT/BOB.

Este modulo lo importan train.py, app.py y los dos monitores de deriva. Que
sea uno solo es lo que garantiza que el modelo que sirve en produccion reciba
exactamente las mismas variables, calculadas igual, que las que vio al
entrenar. Duplicar esta logica en el servicio es la causa mas comun de
"funciona en el notebook pero no en produccion" (training/serving skew).


Tres decisiones de diseno que hay que saber defender
====================================================

1) Frecuencia DIARIA, no horaria
--------------------------------
La serie cruda de usdtbol.com son cotizaciones sueltas del mercado P2P: 2.937
observaciones en 700 dias, con densidad muy desigual (1,2 por dia en 2024;
10 por dia en 2026). Remuestrear eso a frecuencia horaria obliga a rellenar
hacia adelante el 87% de las casillas, y el modelo termina "aprendiendo" que
el precio de la proxima hora es igual al de esta: una metrica altisima sobre
datos que en su mayoria son copias. Agregando por dia, el 71% de los dias
tiene cotizacion real (99% en 2026) y el horizonte -- que hace el tipo de
cambio manana -- es el que economicamente importa.

2) El objetivo es la DIRECCION, no el valor
-------------------------------------------
Se probo predecir el valor exacto con Ridge y XGBoost, en horizontes de 1 a
30 dias, con variables de nivel y de retorno, y con validacion walk-forward.
El baseline ingenuo ("manana vale lo mismo que hoy") gano en todos los casos.
No es un defecto del codigo: a frecuencia diaria un tipo de cambio se comporta
como un paseo aleatorio, y que el baseline sea imbatible en nivel es un
resultado conocido en econometria cambiaria (Meese-Rogoff, 1983).

Predecir el SIGNO del movimiento si es aprendible: hay autocorrelacion en la
direccion y en la volatilidad. Ademas es la pregunta util para alguien que
opera en Bolivia: no "cuanto costara exactamente", sino "conviene comprar hoy
o esperar".

3) Variables ESTACIONARIAS (retornos), no niveles
-------------------------------------------------
Todas las variables continuas son retornos o desviaciones relativas, no
precios en bolivianos. Un modelo entrenado con niveles de 9-10 Bs no sabe que
hacer cuando el precio llega a 12 Bs: esta extrapolando fuera del rango que
vio. Con retornos, un movimiento del 1% es el mismo dato tenga el TC el valor
que tenga, y el modelo sigue siendo valido cuando cambia el nivel.
"""
from __future__ import annotations

import pandas as pd

COLUMNA_PRECIO = "precio"
COLUMNA_OBJETIVO = "sube"

# Dias de historia que hace falta enviar para poder calcular todas las
# variables: desv_media_30d necesita 30 valores rezagados, y el rezago
# consume un dia mas.
MINIMO_DIAS_HISTORIA = 31

# Variables continuas -> se testean con Kolmogorov-Smirnov en el monitor de
# deriva (KS compara distribuciones continuas completas).
FEATURES_CONTINUAS = [
    "ret_1d",           # retorno de ayer: momento de muy corto plazo
    "ret_3d",           # retorno de 3 dias: tendencia recente
    "ret_7d",           # retorno semanal: direccion de fondo
    "vol_7d",           # volatilidad de 7 dias: sube en episodios de estres cambiario
    "desv_media_7d",    # cuan lejos esta el precio de su media semanal (reversion)
    "desv_media_30d",   # lo mismo contra la media mensual: detecta desvios de regimen
]

# Variables discretas -> se testean con PSI sobre frecuencias de categoria.
FEATURES_DISCRETAS = [
    "dia_semana",       # 0=lunes ... 6=domingo
    "es_fin_semana",    # 1 si sabado o domingo: cae el volumen P2P y se abre el spread
]

COLUMNAS_FEATURES = FEATURES_CONTINUAS + FEATURES_DISCRETAS


def cargar_serie_diaria(
    ruta_csv,
    desde: str | None = None,
    hasta: str | None = None,
) -> pd.DataFrame:
    """
    Lee el CSV crudo de usdtbol.com y devuelve la serie agregada por dia.

    Parametros
    ----------
    ruta_csv : ruta al CSV. Se esperan dos columnas (fecha/hora, precio); si
               los nombres no son los estandar se usan las dos primeras.
    desde    : fecha minima inclusive ('YYYY-MM-DD'), o None.
    hasta    : fecha maxima inclusive ('YYYY-MM-DD'), o None.

    El filtrado se hace ANTES de agregar, para que el promedio del dia del
    borde no mezcle cotizaciones de fuera de la ventana pedida.

    Devuelve un DataFrame indexado por dia con:
        precio    -> promedio de las cotizaciones del dia, relleno hacia
                     adelante en los dias sin cotizacion
        obs_real  -> True si ese dia tuvo al menos una cotizacion genuina
    """
    crudo = pd.read_csv(ruta_csv)
    col_fecha, col_precio = crudo.columns[0], crudo.columns[1]

    crudo[col_fecha] = pd.to_datetime(crudo[col_fecha], errors="coerce")
    crudo[col_precio] = pd.to_numeric(crudo[col_precio], errors="coerce")
    crudo = crudo.dropna(subset=[col_fecha, col_precio]).sort_values(col_fecha)

    if desde is not None:
        crudo = crudo[crudo[col_fecha] >= pd.Timestamp(desde)]
    if hasta is not None:
        # +1 dia y "<" para que 'hasta' quede incluido completo
        crudo = crudo[crudo[col_fecha] < pd.Timestamp(hasta) + pd.Timedelta(days=1)]

    if crudo.empty:
        raise ValueError(
            f"No quedaron observaciones en {ruta_csv} para desde={desde} hasta={hasta}."
        )

    serie = crudo.set_index(col_fecha)[col_precio]

    # Promedio del dia: mas representativo que la ultima cotizacion, que puede
    # ser una operacion aislada a una hora rara.
    diario = serie.resample("D").mean()
    hubo_cotizacion = serie.resample("D").count() > 0

    df = pd.DataFrame({COLUMNA_PRECIO: diario, "obs_real": hubo_cotizacion})
    df[COLUMNA_PRECIO] = df[COLUMNA_PRECIO].ffill()
    return df.dropna(subset=[COLUMNA_PRECIO])


def construir_features(df_diario: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega las variables predictoras y la etiqueta.

    Todo se calcula sobre el precio REZAGADO un dia, nunca sobre el precio del
    mismo dia. Al momento de predecir, en produccion, el promedio del dia en
    curso todavia no esta cerrado: usarlo seria fuga de informacion y el
    modelo se veria mucho mejor de lo que realmente es.
    """
    df = df_diario.copy()
    p = df[COLUMNA_PRECIO]
    ayer = p.shift(1)

    df["ret_1d"] = ayer / p.shift(2) - 1
    df["ret_3d"] = ayer / p.shift(4) - 1
    df["ret_7d"] = ayer / p.shift(8) - 1
    df["vol_7d"] = ayer.pct_change().rolling(7).std()
    df["desv_media_7d"] = ayer / ayer.rolling(7).mean() - 1
    df["desv_media_30d"] = ayer / ayer.rolling(30).mean() - 1
    df["dia_semana"] = df.index.dayofweek
    df["es_fin_semana"] = (df.index.dayofweek >= 5).astype(int)

    # Etiqueta: 1 si el tipo de cambio de manana es mayor que el de hoy.
    df[COLUMNA_OBJETIVO] = (p.shift(-1) > p).astype(int)

    # Marca si la etiqueta se apoya en una cotizacion real de manana o en un
    # valor rellenado. Ver filtrar_etiquetas_reales().
    df["etiqueta_real"] = df["obs_real"].shift(-1).astype("boolean").fillna(False).astype(bool)

    return df


def filtrar_etiquetas_reales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deja solo las filas cuya etiqueta viene de una cotizacion genuina.

    Por que es imprescindible: si el dia t+1 no tuvo cotizacion, su precio es
    una copia del de hoy, asi que "sube" da 0 por construccion. Entrenar con
    esas filas le ensena al modelo que lo normal es no subir, y ademas infla
    al baseline de clase mayoritaria (con todos los dias, 72% de las etiquetas
    son 0; filtrando, la reparticion queda 42/58, casi balanceada).

    Las variables SI se calculan sobre la serie completa rellenada, porque los
    rezagos necesitan continuidad de calendario. Lo que se filtra es que filas
    entran al entrenamiento y a la evaluacion, no como se calculan.
    """
    return df[df["etiqueta_real"]]


def division_temporal(df: pd.DataFrame, train_prop: float = 0.8):
    """
    Division cronologica train/test. El test son siempre los dias mas
    recientes.

    Nunca aleatoria: mezclar filas de una serie temporal deja dias futuros en
    el entrenamiento y el modelo se evalua sobre informacion que ya vio. La
    metrica sale inflada y despues falla en produccion.
    """
    X = df[COLUMNAS_FEATURES]
    y = df[COLUMNA_OBJETIVO]
    corte = int(len(X) * train_prop)
    return X.iloc[:corte], X.iloc[corte:], y.iloc[:corte], y.iloc[corte:]


def preparar(
    ruta_csv,
    desde: str | None = None,
    hasta: str | None = None,
    solo_etiquetas_reales: bool = True,
) -> pd.DataFrame:
    """
    Atajo de uso general: cargar + construir variables + limpiar.

    Es la funcion que usan train.py y los monitores, para que los tres partan
    exactamente del mismo conjunto de filas.
    """
    df = construir_features(cargar_serie_diaria(ruta_csv, desde=desde, hasta=hasta))
    df = df.dropna(subset=COLUMNAS_FEATURES + [COLUMNA_OBJETIVO])
    return filtrar_etiquetas_reales(df) if solo_etiquetas_reales else df
