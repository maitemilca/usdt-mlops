"""
Utilidades compartidas por los dos monitores de deriva (Fase 6).

Implementa las dos pruebas estadisticas del proyecto -- Kolmogorov-Smirnov y
PSI -- con sus umbrales explicitos y la justificacion de por que se eligio
cada una.


Que prueba se aplica a cada tipo de variable, y por que
=======================================================

KS (Kolmogorov-Smirnov) para las variables CONTINUAS
----------------------------------------------------
Las seis variables continuas son retornos y desviaciones relativas: valores
reales que pueden tomar infinitos valores distintos. KS compara las dos
funciones de distribucion acumulada completas y se queda con la maxima
distancia vertical entre ellas. No supone ninguna forma de distribucion (no
exige normalidad), que es clave aqui: los retornos cambiarios tienen colas
mucho mas pesadas que una normal.

PSI (Population Stability Index) para las variables DISCRETAS
--------------------------------------------------------------
`dia_semana` toma 7 valores y `es_fin_semana` toma 2. Aplicarles KS no tiene
sentido: la funcion acumulada de una variable con 2 categorias es una
escalera de dos peldanos, y el estadistico pierde interpretacion. PSI compara
directamente las FRECUENCIAS de cada categoria, que es lo que realmente
importa: si un lote trae de golpe el doble de fines de semana, eso se ve.

Ojo con un detalle: la implementacion habitual de PSI reparte los datos en
deciles. Sobre una variable discreta eso produce intervalos vacios o
repetidos y el resultado sale mal. Por eso `calcular_psi_discreto` trabaja
sobre las categorias observadas, no sobre percentiles.


Umbrales, y de donde salen
==========================

KS -> alfa = 0,05
    Es el nivel de significancia estandar en contraste de hipotesis: se
    acepta un 5% de falsas alarmas por puro azar. Es tambien el valor que usa
    el demo de la materia (drift_demo.py).

PSI -> 0,10 y 0,25
    Umbrales consolidados en la industria de riesgo crediticio, donde nacio
    el indice:
        PSI < 0,10          poblacion estable
        0,10 <= PSI < 0,25  cambio moderado, conviene vigilar
        PSI >= 0,25         cambio importante, dispara alerta


Una advertencia sobre el tamano de muestra
===========================================
El p-valor de KS es cada vez mas sensible cuanto mas grande es la muestra:
con miles de observaciones, diferencias irrelevantes salen "significativas".
Por eso los reportes muestran SIEMPRE el estadistico KS (que va de 0 a 1 y si
es comparable entre lotes de distinto tamano) junto al veredicto binario. El
estadistico es el tamano del efecto; el p-valor solo dice si es distinguible
del azar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

ALFA_KS = 0.05
PSI_UMBRAL_MODERADO = 0.10
PSI_UMBRAL_ALERTA = 0.25

# Suelo de probabilidad: evita dividir por cero y log(0) cuando una categoria
# aparece en un lote y no en el otro.
EPSILON = 1e-6


def calcular_psi_discreto(referencia, actual) -> float:
    """
    PSI sobre las frecuencias de categoria de una variable discreta.

        PSI = suma sobre categorias de  (p_actual - p_ref) * ln(p_actual / p_ref)

    Es simetrico y siempre positivo: vale 0 si las dos reparticiones son
    identicas y crece cuanto mas se separan.
    """
    ref = pd.Series(referencia).value_counts(normalize=True)
    act = pd.Series(actual).value_counts(normalize=True)

    # Union de categorias: una categoria ausente en un lado cuenta como
    # frecuencia ~0, no se ignora (su desaparicion ES la senal de deriva).
    categorias = ref.index.union(act.index)
    p_ref = ref.reindex(categorias, fill_value=0.0).clip(lower=EPSILON)
    p_act = act.reindex(categorias, fill_value=0.0).clip(lower=EPSILON)

    return float(np.sum((p_act - p_ref) * np.log(p_act / p_ref)))


def interpretar_psi(valor: float) -> str:
    if valor < PSI_UMBRAL_MODERADO:
        return "estable"
    if valor < PSI_UMBRAL_ALERTA:
        return "cambio moderado"
    return "cambio importante"


def evaluar_ks(nombre: str, referencia, actual) -> dict:
    """Prueba KS de dos muestras sobre una variable continua."""
    estadistico, p_valor = ks_2samp(np.asarray(referencia, dtype=float),
                                    np.asarray(actual, dtype=float))
    return {
        "variable": nombre,
        "prueba": "KS",
        "estadistico": float(estadistico),
        "p_valor": float(p_valor),
        "hay_deriva": bool(p_valor < ALFA_KS),
    }


def evaluar_psi(nombre: str, referencia, actual) -> dict:
    """PSI sobre una variable discreta."""
    psi = calcular_psi_discreto(referencia, actual)
    return {
        "variable": nombre,
        "prueba": "PSI",
        "estadistico": psi,
        "p_valor": None,
        "interpretacion": interpretar_psi(psi),
        "hay_deriva": bool(psi >= PSI_UMBRAL_ALERTA),
    }


def evaluar_lote(referencia: pd.DataFrame, actual: pd.DataFrame,
                 continuas: list[str], discretas: list[str]) -> list[dict]:
    """Corre la prueba que corresponde a cada variable del lote completo."""
    resultados = [evaluar_ks(c, referencia[c], actual[c]) for c in continuas]
    resultados += [evaluar_psi(d, referencia[d], actual[d]) for d in discretas]
    return resultados


def hay_deriva(resultados: list[dict]) -> bool:
    """Veredicto agregado: basta con que una variable derive."""
    return any(r["hay_deriva"] for r in resultados)


def imprimir_reporte(titulo: str, resultados: list[dict], n_ref: int, n_act: int) -> bool:
    """
    Imprime el reporte de un lote y devuelve el veredicto.

    True = hay deriva (rojo). False = sin deriva (verde).
    """
    rojo = hay_deriva(resultados)
    print(f"\n{'=' * 72}")
    print(f"{titulo}")
    print(f"referencia: {n_ref} filas   |   lote evaluado: {n_act} filas")
    print("=" * 72)

    for r in resultados:
        if r["prueba"] == "KS":
            marca = "DERIVA" if r["hay_deriva"] else "estable"
            print(f"  KS   {r['variable']:<16} estadistico={r['estadistico']:.4f}  "
                  f"p={r['p_valor']:.3e}   -> {marca}")
        else:
            marca = "DERIVA" if r["hay_deriva"] else r["interpretacion"]
            print(f"  PSI  {r['variable']:<16} psi={r['estadistico']:.4f}"
                  f"{'':<20}-> {marca}")

    print(f"\n  VEREDICTO: {'ROJO (deriva detectada)' if rojo else 'VERDE (sin deriva)'}")
    return rojo
