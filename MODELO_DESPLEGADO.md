# Modelo desplegado

> Generado automaticamente por `src/actualizar_ficha.py` a partir del Model
> Registry. No editar a mano.

| Campo | Valor |
|---|---|
| Nombre registrado | `tc-usdt-bob-direccion` |
| Version | **2** |
| Alias de despliegue | `champion` |
| Run de origen | `67148fe2b4c5476a839acd710e977f95` |
| Experimento | `tc_usdt_bolivia_diario` |
| Corrida ganadora | `xgboost_cfg3` |
| Hiperparametros | learning_rate=0.03, max_depth=4, n_estimators=500 |
| exactitud_balanceada_cv (criterio de seleccion) | 0.5762 |
| Exactitud balanceada en test | 0.5685 |
| ROC AUC en test | 0.5499 |
| Datos hasta | 2026-07-31 |
| Filas train / test | 390 / 98 |
| Semilla | 42 |
| Ficha actualizada el | 2026-08-04T20:48:15+00:00 |
| Python | 3.12.3 |

## Descripcion registrada

Reentrenamiento disparado por el monitor de concept drift: la exactitud balanceada cayo por debajo del azar dos meses seguidos tras la flexibilizacion cambiaria del BCB. Incluye los datos posteriores al cambio de regimen.

Corrida ganadora: xgboost_cfg3 (n_estimators=500, max_depth=4, learning_rate=0.03)
exactitud_balanceada_cv (criterio de seleccion): 0.5762
Exactitud balanceada en test: 0.5685
ROC AUC en test: 0.5499
Datos hasta: 2026-07-31
Filas de entrenamiento: 390

---

El servicio de inferencia carga este modelo por la referencia
`models:/tc-usdt-bob-direccion@champion`, nunca por una ruta
de archivo. Mover el alias a otra version, reconstruir la imagen y reiniciar el
despliegue es todo lo que hace falta para cambiar el modelo en produccion.
