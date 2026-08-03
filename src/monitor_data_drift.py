"""
Fase 6.1 -- Monitor de DATA DRIFT (deriva de datos).

Compara la distribucion de cada variable de entrada de un lote nuevo contra el
baseline de entrenamiento (el X_train de la version 1).

Esto NO es un reporte informativo: es una PUERTA. Termina con codigo de salida
0 (verde, sin deriva) o 1 (rojo, deriva detectada), de modo que se pueda
encadenar en un pipeline y detener un despliegue. La consigna pide justamente
que la prueba falle en rojo con datos derivados y pase en verde con datos del
mismo origen.

Escenarios disponibles
----------------------
  control      Mitad aleatoria del propio X_train. Misma distribucion, solo
               barajada. DEBE dar VERDE: es la prueba de que el detector no
               inventa falsas alarmas.

  pre_flex     Holdout real entre la fecha de corte y la flexibilizacion
               (2025-12-12 a 2026-06-28). Datos reales posteriores al
               entrenamiento, mismo regimen cambiario.

  post_flex    Holdout real desde el 29-jun-2026: el cambio de regimen del
               BCB, con el TCO pasando de 6,96 a 12,15 Bs. Deriva REAL y
               documentada, no inyectada.

  sintetico    Deriva inyectada a proposito (retornos multiplicados por 5 y
               desplazados). Control positivo: confirma que el detector
               dispara cuando la deriva es innegable.

  todos        Corre los cuatro y devuelve el resumen.

Uso:
    python monitor_data_drift.py --escenario control     # espera VERDE, sale 0
    python monitor_data_drift.py --escenario post_flex   # espera ROJO, sale 1
    python monitor_data_drift.py --escenario todos
"""
from __future__ import annotations

import argparse
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as cfg
from drift_common import evaluar_lote, hay_deriva, imprimir_reporte
from features import (
    COLUMNAS_FEATURES,
    FEATURES_CONTINUAS,
    FEATURES_DISCRETAS,
    division_temporal,
    preparar,
)


def cargar_baseline() -> pd.DataFrame:
    """
    El baseline es el X_train exacto con el que se entreno la version 1.

    Importa que sea el train y no todo el conjunto: es la poblacion que el
    modelo efectivamente vio. Comparar contra datos que el modelo nunca uso
    mediria otra cosa.
    """
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    X_train, _, _, _ = division_temporal(df, cfg.TRAIN_PROP)
    return X_train


def lote_control(baseline: pd.DataFrame) -> pd.DataFrame:
    """
    Mitad aleatoria del baseline: la referencia de "verde".

    Se usa un reparto aleatorio y no el X_test cronologico a proposito. El
    X_test es un tramo posterior en el tiempo, y en una serie cambiaria eso ya
    trae un cambio de nivel: marcaria deriva aunque no haya ningun problema.
    Barajando al azar, las dos mitades vienen de la misma distribucion por
    construccion, que es lo que se necesita para verificar que el detector no
    produce falsos positivos.
    """
    generador = np.random.default_rng(cfg.RANDOM_SEED)
    indices = generador.permutation(len(baseline))
    return baseline.iloc[indices[len(indices) // 2:]]


def lote_sintetico(baseline: pd.DataFrame) -> pd.DataFrame:
    """
    Deriva inyectada deliberadamente: control positivo del detector.

    Se amplifican los retornos por 5 y se los desplaza medio punto porcentual,
    imitando un salto de volatilidad y una devaluacion sostenida. Es el
    escenario que la consigna llama "inyectar datos derivados".
    """
    lote = baseline.copy()
    for columna in FEATURES_CONTINUAS:
        lote[columna] = lote[columna] * 5.0 + 0.005
    return lote


def lote_real(desde: str, hasta: str | None = None) -> pd.DataFrame:
    """
    Recorta un tramo del holdout, construyendo las variables sobre la serie
    COMPLETA y filtrando por fecha despues.

    Es importante hacerlo en este orden. Si se cargara la serie ya recortada,
    `desv_media_30d` necesitaria 30 dias de calentamiento y se comeria el
    primer mes del lote: el tramo posterior a la flexibilizacion, que dura
    poco mas de 30 dias, quedaria reducido a 2 filas. Construyendo sobre la
    serie completa, cada dia del lote tiene su historia real detras, que es
    ademas lo que ocurre en produccion.
    """
    completo = preparar(cfg.CSV_COMPLETO)
    tramo = completo[completo.index >= pd.Timestamp(desde)]
    if hasta is not None:
        tramo = tramo[tramo.index < pd.Timestamp(hasta)]
    return tramo[COLUMNAS_FEATURES]


def obtener_lote(nombre: str, baseline: pd.DataFrame) -> pd.DataFrame:
    if nombre == "control":
        return lote_control(baseline)
    if nombre == "sintetico":
        return lote_sintetico(baseline)
    if nombre == "pre_flex":
        return lote_real(cfg.FECHA_CORTE_V1, cfg.FECHA_FLEXIBILIZACION)
    if nombre == "post_flex":
        return lote_real(cfg.FECHA_FLEXIBILIZACION)
    raise ValueError(f"Escenario desconocido: {nombre}")


TITULOS = {
    "control": "CONTROL -- mitad aleatoria de X_train (se espera VERDE)",
    "pre_flex": f"LOTE REAL -- de {cfg.FECHA_CORTE_V1} a la flexibilizacion",
    "post_flex": f"LOTE REAL -- desde la flexibilizacion del {cfg.FECHA_FLEXIBILIZACION}",
    "sintetico": "SINTETICO -- deriva inyectada a proposito (se espera ROJO)",
}


def graficar(baseline: pd.DataFrame, lotes: dict[str, pd.DataFrame]) -> None:
    """Compara la distribucion de ret_1d del baseline contra cada lote."""
    cfg.DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    n = len(lotes)
    fig, ejes = plt.subplots(n, 1, figsize=(10, 3.1 * n), squeeze=False)

    for eje, (nombre, lote) in zip(ejes[:, 0], lotes.items()):
        eje.hist(baseline["ret_1d"], bins=45, alpha=0.6, density=True,
                 label=f"Baseline X_train (n={len(baseline)})")
        eje.hist(lote["ret_1d"], bins=45, alpha=0.6, density=True,
                 label=f"{nombre} (n={len(lote)})")
        eje.set_title(TITULOS[nombre], fontsize=10)
        eje.set_xlabel("ret_1d (retorno diario)")
        eje.set_ylabel("densidad")
        eje.legend(fontsize=8)
        eje.grid(alpha=0.25)

    fig.suptitle("Fase 6.1 -- Data drift: distribucion del retorno diario por escenario")
    fig.tight_layout()
    destino = cfg.DIR_RESULTADOS / "data_drift.png"
    fig.savefig(destino, dpi=140)
    plt.close(fig)
    print(f"\nGrafico guardado en {destino.relative_to(cfg.RAIZ)}")


def main(escenario: str) -> int:
    baseline = cargar_baseline()
    nombres = list(TITULOS) if escenario == "todos" else [escenario]

    lotes, veredictos = {}, {}
    for nombre in nombres:
        lote = obtener_lote(nombre, baseline)
        lotes[nombre] = lote
        resultados = evaluar_lote(baseline, lote, FEATURES_CONTINUAS, FEATURES_DISCRETAS)
        veredictos[nombre] = imprimir_reporte(
            TITULOS[nombre], resultados, len(baseline), len(lote)
        )

    graficar(baseline, lotes)

    print(f"\n{'=' * 72}\nRESUMEN\n{'=' * 72}")
    for nombre, rojo in veredictos.items():
        esperado = "VERDE" if nombre == "control" else "ROJO"
        obtenido = "ROJO" if rojo else "VERDE"
        marca = "ok" if obtenido == esperado else "INESPERADO"
        print(f"  {nombre:<12} esperado={esperado:<6} obtenido={obtenido:<6} [{marca}]")

    # Codigo de salida: el control no debe disparar la puerta; cualquier lote
    # real o sintetico con deriva si la dispara.
    dispara = any(rojo for nombre, rojo in veredictos.items() if nombre != "control")
    if veredictos.get("control", False):
        print("\nATENCION: el control dio ROJO. El detector esta produciendo falsos "
              "positivos y hay que revisar los umbrales antes de confiar en el.")
        dispara = True

    print(f"\nCodigo de salida: {1 if dispara else 0} "
          f"({'ROJO -- deriva detectada' if dispara else 'VERDE -- sin deriva'})")
    return 1 if dispara else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--escenario", default="todos",
                   choices=["control", "pre_flex", "post_flex", "sintetico", "todos"])
    args = p.parse_args()
    sys.exit(main(args.escenario))
