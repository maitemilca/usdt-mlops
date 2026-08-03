"""
Pruebas automatizadas del sistema de deteccion de deriva (consigna Fase 6).

Que se esta probando aqui, y que no
-----------------------------------
Estas pruebas verifican que el DETECTOR funciona: que da verde cuando los
datos vienen del mismo origen que el entrenamiento y rojo cuando hay deriva.
Es control de calidad del monitor, y por eso se espera que todas pasen.

La puerta operativa -- la que efectivamente FALLA en rojo cuando llega un lote
derivado -- son los scripts `src/monitor_data_drift.py` y
`src/monitor_concept_drift.py`, que terminan con codigo de salida 1. Esa
separacion es intencional: un monitor que se cae solo no se puede distinguir
de un monitor roto, asi que primero se prueba que el detector es confiable y
despues se lo usa como puerta.

Ejecutar:
    pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config as cfg  # noqa: E402
from drift_common import (  # noqa: E402
    ALFA_KS,
    PSI_UMBRAL_ALERTA,
    calcular_psi_discreto,
    evaluar_ks,
    evaluar_lote,
    evaluar_psi,
    hay_deriva,
)
from features import (  # noqa: E402
    COLUMNAS_FEATURES,
    FEATURES_CONTINUAS,
    FEATURES_DISCRETAS,
    division_temporal,
    preparar,
)
from monitor_data_drift import cargar_baseline, lote_control, lote_real, lote_sintetico  # noqa: E402


# --------------------------------------------------------------------------
# Datos compartidos: se cargan una sola vez para toda la sesion de pruebas.
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def baseline() -> pd.DataFrame:
    return cargar_baseline()


# --------------------------------------------------------------------------
# 1. Las pruebas estadisticas, aisladas
# --------------------------------------------------------------------------
def test_ks_no_detecta_deriva_en_muestras_de_la_misma_distribucion():
    """Dos muestras de la misma normal: KS no debe marcar deriva."""
    generador = np.random.default_rng(cfg.RANDOM_SEED)
    a = generador.normal(0, 1, 500)
    b = generador.normal(0, 1, 500)

    resultado = evaluar_ks("prueba", a, b)

    assert resultado["p_valor"] > ALFA_KS
    assert resultado["hay_deriva"] is False


def test_ks_detecta_un_desplazamiento_de_media():
    """Dos normales separadas por 2 desviaciones: KS debe marcar deriva."""
    generador = np.random.default_rng(cfg.RANDOM_SEED)
    a = generador.normal(0, 1, 500)
    b = generador.normal(2, 1, 500)

    resultado = evaluar_ks("prueba", a, b)

    assert resultado["p_valor"] < ALFA_KS
    assert resultado["hay_deriva"] is True
    assert resultado["estadistico"] > 0.5


def test_psi_vale_cero_con_reparticiones_identicas():
    categorias = [0, 1, 2, 3, 4, 5, 6] * 30
    assert calcular_psi_discreto(categorias, categorias) == pytest.approx(0.0, abs=1e-9)


def test_psi_dispara_cuando_cambia_la_reparticion_de_categorias():
    """Referencia repartida uniforme; lote concentrado en una sola categoria."""
    referencia = [0, 1, 2, 3, 4, 5, 6] * 30
    actual = [0] * 200

    psi = calcular_psi_discreto(referencia, actual)

    assert psi >= PSI_UMBRAL_ALERTA
    assert evaluar_psi("dia_semana", referencia, actual)["hay_deriva"] is True


def test_psi_no_ignora_una_categoria_que_desaparece():
    """
    Que una categoria deje de aparecer ES deriva, no un dato faltante.

    Si la implementacion recorriera solo las categorias del lote nuevo, este
    caso pasaria desapercibido.
    """
    referencia = [0, 1, 2, 3] * 50
    actual = [0, 1] * 100  # desaparecen las categorias 2 y 3

    assert calcular_psi_discreto(referencia, actual) >= PSI_UMBRAL_ALERTA


# --------------------------------------------------------------------------
# 2. Data drift sobre los datos reales del proyecto
# --------------------------------------------------------------------------
def test_control_no_produce_falsos_positivos(baseline):
    """
    VERDE obligatorio: el lote de control es una mitad aleatoria del propio
    baseline, o sea la misma distribucion barajada. Si esto diera rojo, el
    detector estaria inventando alarmas y ningun otro resultado seria creible.
    """
    control = lote_control(baseline)
    resultados = evaluar_lote(baseline, control, FEATURES_CONTINUAS, FEATURES_DISCRETAS)

    derivadas = [r["variable"] for r in resultados if r["hay_deriva"]]
    assert not derivadas, f"Falsos positivos en: {derivadas}"


def test_lote_post_flexibilizacion_marca_deriva(baseline):
    """
    ROJO obligatorio: el tramo posterior al 29-jun-2026 es el cambio de
    regimen cambiario real del BCB. Si el detector no lo viera, no serviria.
    """
    lote = lote_real(cfg.FECHA_FLEXIBILIZACION)
    resultados = evaluar_lote(baseline, lote, FEATURES_CONTINUAS, FEATURES_DISCRETAS)

    assert hay_deriva(resultados)


def test_deriva_inyectada_a_proposito_marca_rojo(baseline):
    """
    ROJO obligatorio: es el escenario textual de la consigna, "inyectar datos
    derivados". Control positivo del detector.
    """
    resultados = evaluar_lote(baseline, lote_sintetico(baseline),
                              FEATURES_CONTINUAS, FEATURES_DISCRETAS)

    assert hay_deriva(resultados)
    # No basta con que dispare una variable: la deriva se inyecto en las seis
    # continuas y las seis deberian marcarla.
    continuas_con_deriva = [
        r["variable"] for r in resultados
        if r["prueba"] == "KS" and r["hay_deriva"]
    ]
    assert len(continuas_con_deriva) == len(FEATURES_CONTINUAS)


# --------------------------------------------------------------------------
# 3. Coherencia de los datos y las variables
# --------------------------------------------------------------------------
def test_las_etiquetas_solo_salen_de_cotizaciones_reales():
    """
    Ninguna fila de entrenamiento puede tener una etiqueta derivada de un dia
    rellenado: en esos dias el precio es una copia del anterior y "sube"
    valdria 0 por construccion, no porque el mercado se haya movido.
    """
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    assert df["etiqueta_real"].all()


def test_la_division_temporal_no_mezcla_el_futuro_con_el_pasado():
    """Toda fecha del test tiene que ser posterior a toda fecha del train."""
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    X_train, X_test, _, _ = division_temporal(df, cfg.TRAIN_PROP)

    assert X_train.index.max() < X_test.index.min()


def test_no_quedan_valores_faltantes_en_las_variables():
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    assert df[COLUMNAS_FEATURES].isna().sum().sum() == 0


def test_las_clases_estan_razonablemente_balanceadas():
    """
    Si una clase se llevara mas del 80%, la exactitud balanceada perderia
    sentido y habria que replantear el objetivo.
    """
    df = preparar(cfg.CSV_COMPLETO, hasta=cfg.FECHA_CORTE_V1)
    proporcion_alza = df["sube"].mean()

    assert 0.2 < proporcion_alza < 0.8, f"Clases muy desbalanceadas: {proporcion_alza:.2%} al alza"
