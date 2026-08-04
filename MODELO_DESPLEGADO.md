# Modelo desplegado

> Generado automaticamente por `src/train.py`. No editar a mano.

| Campo | Valor |
|---|---|
| Nombre registrado | `tc-usdt-bob-direccion` |
| Version | **1** |
| Alias de despliegue | `champion` |
| Run de origen | `a6fd0fb36253435ba404fa3303bedcfc` |
| Experimento | `tc_usdt_bolivia_diario` |
| Corrida ganadora | `xgboost_cfg2` |
| Hiperparametros | n_estimators=300, max_depth=3, learning_rate=0.05 |
| exactitud_balanceada_cv (criterio de seleccion) | 0.5860 |
| Exactitud balanceada en test | 0.6410 |
| ROC AUC en test | 0.6213 |
| Datos hasta | 2025-12-11 |
| Filas train / test | 207 / 52 |
| Semilla | 42 |
| Motivo | Version inicial: entrenada antes de la flexibilizacion cambiaria del BCB. |
| Entrenado el | 2026-08-03T19:05:05+00:00 |
| Python | 3.12.3 |

El servicio de inferencia carga este modelo por la referencia
`models:/tc-usdt-bob-direccion@champion`, nunca por una ruta
de archivo. Mover el alias a otra version y reiniciar los pods es todo lo que
hace falta para cambiar el modelo en produccion.
