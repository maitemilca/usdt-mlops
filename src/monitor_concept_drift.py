"""
Fase 6.2 -- Monitor de CONCEPT DRIFT (deriva de concepto).

Data drift es que cambien las ENTRADAS. Concept drift es que cambie la
RELACION entre las entradas y la respuesta: las entradas pueden verse
identicas y aun asi el modelo empieza a equivocarse, porque la regla que
generaba la respuesta ya no es la misma.

Aqui se mide directamente sobre el modelo desplegado: se le pide que prediga
lotes mensuales sucesivos del holdout real y se sigue como evoluciona su
exactitud balanceada. Igual que el monitor de data drift, esto es una PUERTA:
termina en 0 (verde) o 1 (rojo).

Que contiene el reporte
-----------------------
  1. Curva temporal de exactitud balanceada por mes sobre el holdout real,
     con la fecha de la flexibilizacion cambiaria marcada.
  2. Escenario sintetico de control: se invierten las etiquetas de un
     subconjunto (exactamente lo que sugiere la consigna) para confirmar que
     el detector dispara cuando el concept drift es innegable.
  3. Criterio explicito de reentrenamiento, y si se habria disparado.
  4. Discusion del retraso de etiqueta.

Uso:
    python monitor_concept_drift.py
    python monitor_concept_drift.py --escenario sintetico
"""
from __future__ import annotations

import argparse
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

import config as cfg
from features import COLUMNA_OBJETIVO, COLUMNAS_FEATURES, division_temporal, preparar

# --- Criterio de reentrenamiento -----------------------------------------
# Se dispara la alarma si la exactitud balanceada del lote cae por debajo de
# 0,50 durante 2 meses seguidos.
#
# Por que 0,50 y no un porcentaje de caida respecto de la referencia: 0,50 es
# el valor exacto del azar en esta metrica. Por debajo de ese numero el modelo
# no solo dejo de aportar, sino que esta induciendo decisiones peores que
# tirar una moneda. Es un umbral con significado propio, no un numero elegido
# a dedo.
#
# Por que 2 meses y no 1: cada lote mensual tiene ~25 dias con etiqueta real.
# Con esa cantidad, la metrica de un solo mes se mueve varios puntos por puro
# azar. Exigir dos meses consecutivos filtra el ruido sin tardar tanto en
# reaccionar como para que el modelo siga tomando malas decisiones meses.
UMBRAL_EXACTITUD = 0.50
LOTES_SOSTENIDOS = 2


def cargar_modelo_desplegado():
    """
    Carga el modelo por la MISMA referencia de registro que usa el servicio.

    Es deliberado: se monitorea exactamente el artefacto que esta respondiendo
    en produccion, no una copia reentrenada que podria diferir.
    """
    cfg.configurar_mlflow()
    referencia = f"models:/{cfg.REGISTERED_MODEL_NAME}@{cfg.DEPLOYMENT_ALIAS}"
    ultimo_error = None
    for sabor in (mlflow.sklearn, mlflow.xgboost):
        try:
            modelo = sabor.load_model(referencia)
            version = mlflow.MlflowClient().get_model_version_by_alias(
                cfg.REGISTERED_MODEL_NAME, cfg.DEPLOYMENT_ALIAS
            )
            return modelo, version
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
    raise RuntimeError(f"No se pudo cargar {referencia}: {ultimo_error}")


def exactitud_referencia(modelo) -> float:
    """Exactitud balanceada del modelo sobre el test de la Fase 1: la linea base."""
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    _, X_test, _, y_test = division_temporal(df, cfg.TRAIN_PROP)
    return float(balanced_accuracy_score(y_test, modelo.predict(X_test)))


def curva_mensual(modelo) -> pd.DataFrame:
    """
    Exactitud balanceada mes a mes sobre todo el holdout real.

    Las variables se construyen sobre la serie completa y despues se recorta
    el holdout, para que cada dia tenga su historia real detras (misma razon
    que en el monitor de data drift).
    """
    completo = preparar(cfg.CSV_COMPLETO)
    holdout = completo[completo.index >= pd.Timestamp(cfg.FECHA_CORTE_V1)].copy()
    holdout["prediccion"] = modelo.predict(holdout[COLUMNAS_FEATURES])

    filas = []
    for periodo, grupo in holdout.groupby(pd.Grouper(freq="MS")):
        # Un mes con una sola clase no permite calcular exactitud balanceada.
        if len(grupo) < 5 or grupo[COLUMNA_OBJETIVO].nunique() < 2:
            continue
        filas.append({
            "mes": periodo,
            "n": len(grupo),
            "pct_al_alza": float(grupo[COLUMNA_OBJETIVO].mean()),
            "exactitud_balanceada": float(
                balanced_accuracy_score(grupo[COLUMNA_OBJETIVO], grupo["prediccion"])
            ),
        })

    return pd.DataFrame(filas).set_index("mes")


FRACCIONES_INVERSION = [0.0, 0.25, 0.50, 0.75, 1.0]


def escenario_sintetico(modelo) -> pd.DataFrame:
    """
    Control positivo: se invierten las etiquetas de una fraccion creciente del
    test, dejando las ENTRADAS intactas.

    Es el escenario que sugiere la consigna ("invirtiendo o reasignando
    etiquetas en un subconjunto"). Como las variables de entrada no se tocan,
    cualquier degradacion es concept drift puro: la relacion entrada-respuesta
    cambio y el modelo quedo desactualizado.

    Se recorre un barrido de intensidad en vez de un solo caso porque es lo
    que muestra la SENSIBILIDAD del detector. Y hay un resultado que conviene
    entender antes de la defensa: invirtiendo justo la mitad, la exactitud
    balanceada vuelve a ~0,50 y el detector NO dispara. No es un fallo. Con la
    mitad de las etiquetas dadas vuelta el modelo acierta en un tramo y falla
    en el otro, y su rendimiento real ES el del azar. El detector esta
    reportando la verdad; lo que revela el barrido es que una inversion
    parcial es el peor caso para detectar, porque se disfraza de ruido.
    """
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    _, X_test, _, y_test = division_temporal(df, cfg.TRAIN_PROP)
    prediccion = modelo.predict(X_test)

    filas = []
    for fraccion in FRACCIONES_INVERSION:
        y_alterada = y_test.copy()
        n_invertidas = int(len(y_alterada) * fraccion)
        if n_invertidas:
            # Se invierten las ultimas n: simula que la regla cambio a partir
            # de un momento dado, que es como ocurre en la realidad.
            y_alterada.iloc[-n_invertidas:] = 1 - y_alterada.iloc[-n_invertidas:]

        exactitud = float(balanced_accuracy_score(y_alterada, prediccion))
        filas.append({
            "fraccion_invertida": fraccion,
            "n_invertidas": n_invertidas,
            "exactitud_balanceada": exactitud,
            "dispara": exactitud < UMBRAL_EXACTITUD,
        })

    return pd.DataFrame(filas)


def evaluar_criterio(curva: pd.DataFrame) -> pd.Timestamp | None:
    """Devuelve el mes en que se habria disparado la alarma, o None."""
    racha = 0
    for mes, fila in curva.iterrows():
        racha = racha + 1 if fila["exactitud_balanceada"] < UMBRAL_EXACTITUD else 0
        if racha >= LOTES_SOSTENIDOS:
            return mes
    return None


def graficar(curva: pd.DataFrame, referencia: float, disparo) -> None:
    cfg.DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    fig, eje = plt.subplots(figsize=(12, 5))

    eje.plot(curva.index, curva["exactitud_balanceada"], marker="o",
             linewidth=2, label="Exactitud balanceada del lote")
    eje.axhline(referencia, color="green", linestyle="--",
                label=f"Referencia en test Fase 1 ({referencia:.3f})")
    eje.axhline(UMBRAL_EXACTITUD, color="red", linestyle="--",
                label=f"Umbral de alarma = azar ({UMBRAL_EXACTITUD:.2f})")
    eje.axvline(pd.Timestamp(cfg.FECHA_FLEXIBILIZACION), color="black", linestyle=":",
                label=f"Flexibilizacion cambiaria ({cfg.FECHA_FLEXIBILIZACION})")

    if disparo is not None:
        eje.axvspan(disparo, curva.index.max(), color="red", alpha=0.08)
        eje.annotate("alarma de reentrenamiento", xy=(disparo, UMBRAL_EXACTITUD),
                     xytext=(10, 30), textcoords="offset points", color="red", fontsize=9,
                     arrowprops={"arrowstyle": "->", "color": "red"})

    eje.set_title("Fase 6.2 -- Concept drift: degradacion del modelo desplegado sobre el holdout real")
    eje.set_xlabel("Mes")
    eje.set_ylabel("Exactitud balanceada")
    eje.set_ylim(0, 1)
    eje.legend(fontsize=8, loc="lower left")
    eje.grid(alpha=0.3)
    fig.tight_layout()

    destino = cfg.DIR_RESULTADOS / "concept_drift.png"
    fig.savefig(destino, dpi=140)
    plt.close(fig)
    print(f"\nGrafico guardado en {destino.relative_to(cfg.RAIZ)}")


TEXTO_RETRASO_ETIQUETA = """
RETRASO DE ETIQUETA (label delay)
---------------------------------
Todo lo anterior supone que ya se conoce la respuesta correcta de cada dia.
En produccion eso no pasa nunca en el momento de predecir.

En este modelo el retraso es corto: la etiqueta de hoy (si el tipo de cambio
subio o no) se sabe manana. Es una situacion mucho mas comoda que la de un
modelo de riesgo crediticio, donde confirmar un incumplimiento puede tomar
meses. Pero el retraso existe, y con lotes mensuales significa que un mes malo
recien se puede confirmar cuando ya termino.

Que se hace mientras tanto:

  1. El monitor de data drift (Fase 6.1) es la alerta temprana. No necesita
     etiquetas: compara solo las entradas. Si las entradas se van del rango
     conocido, hay motivo para desconfiar del modelo aunque todavia no se
     pueda medir su error.

  2. Se vigila la distribucion de las probabilidades que devuelve el modelo.
     Si empieza a responder casi siempre lo mismo, o se concentra alrededor
     de 0,5, esta perdiendo capacidad de discriminar. Tampoco necesita
     etiquetas.

  3. Se usa el error del lote anterior como estimacion del actual. A esta
     granularidad los regimenes cambiarios cambian en semanas o meses, no de
     un dia para otro, asi que el ultimo error medido es una aproximacion
     razonable mientras llega el definitivo.

  4. Ante la duda, se degrada con cuidado: se acompana la respuesta con la
     probabilidad y se avisa cuando la confianza es baja, en vez de presentar
     una direccion como si fuera segura.
"""


def main(escenario: str) -> int:
    modelo, version = cargar_modelo_desplegado()
    print(f"Modelo monitoreado: {cfg.REGISTERED_MODEL_NAME} v{version.version} "
          f"(alias {cfg.DEPLOYMENT_ALIAS}, run {version.run_id})")

    referencia = exactitud_referencia(modelo)
    print(f"Exactitud balanceada de referencia (test de la Fase 1): {referencia:.4f}")

    if escenario == "sintetico":
        print(f"\n{'=' * 72}\nCONTROL SINTETICO -- barrido de inversion de etiquetas\n{'=' * 72}")
        print("  Las variables de entrada NO se tocan: solo cambia la relacion")
        print("  entrada-respuesta. Toda degradacion es concept drift puro.\n")

        tabla = escenario_sintetico(modelo)
        for _, fila in tabla.iterrows():
            estado = "DISPARA (rojo)" if fila["dispara"] else "no dispara"
            print(f"  {fila['fraccion_invertida']:>5.0%} invertido "
                  f"({int(fila['n_invertidas']):>3d} etiquetas)  "
                  f"exactitud balanceada = {fila['exactitud_balanceada']:.4f}   -> {estado}")

        # La exigencia minima al detector: con TODAS las etiquetas invertidas
        # tiene que disparar. Si no lo hace, el monitor no sirve.
        inversion_total = tabla.iloc[-1]
        rojo = bool(inversion_total["dispara"])

        print(f"\n  Referencia sin manipular: {referencia:.4f}")
        print(f"\n  VEREDICTO con inversion total: "
              f"{'ROJO -- el detector dispara, es correcto' if rojo else 'VERDE -- el detector NO dispara: hay que revisarlo'}")
        print("\n  Nota: con el 50% invertido el detector no dispara, y esta bien. Con")
        print("  la mitad de las etiquetas dadas vuelta el modelo acierta en un tramo")
        print("  y falla en el otro, asi que su rendimiento real es el del azar: el")
        print("  monitor esta reportando la verdad. Lo que muestra el barrido es que")
        print("  una inversion parcial es el caso mas dificil de detectar.")

        print(f"\nCodigo de salida: {1 if rojo else 0}")
        return 1 if rojo else 0

    curva = curva_mensual(modelo)
    print(f"\n{'=' * 72}\nCURVA MENSUAL SOBRE EL HOLDOUT REAL\n{'=' * 72}")
    tabla = curva.copy()
    tabla.index = tabla.index.strftime("%Y-%m")
    print(tabla.to_string(float_format=lambda x: f"{x:.4f}"))

    disparo = evaluar_criterio(curva)
    print(f"\n{'=' * 72}\nCRITERIO DE REENTRENAMIENTO\n{'=' * 72}")
    print(f"  Alarma si la exactitud balanceada < {UMBRAL_EXACTITUD:.2f} (azar) "
          f"durante {LOTES_SOSTENIDOS} meses seguidos.")
    if disparo is not None:
        print(f"\n  ALARMA: se habria disparado en {disparo.strftime('%Y-%m')}.")
        print(f"  Accion: reentrenar incorporando los datos nuevos y registrar una "
              f"version nueva en el Model Registry.")
    else:
        print("\n  El criterio no se activo en ningun tramo del holdout.")

    graficar(curva, referencia, disparo)
    print(TEXTO_RETRASO_ETIQUETA)

    print(f"Codigo de salida: {1 if disparo is not None else 0} "
          f"({'ROJO -- concept drift sostenido' if disparo is not None else 'VERDE'})")
    return 1 if disparo is not None else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--escenario", default="real", choices=["real", "sintetico"])
    args = p.parse_args()
    sys.exit(main(args.escenario))
