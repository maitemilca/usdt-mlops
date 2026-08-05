"""
Regenera MODELO_DESPLEGADO.md a partir del estado real del Model Registry.

Por que hace falta
------------------
`train.py` escribe la ficha solo cuando el entrenamiento ademas mueve el
alias. Pero promover una version a produccion es una decision separada: se
puede registrar una version con `--sin-alias` y decidir despues si se
despliega. Cuando esa promocion se hace a mano, la ficha queda desactualizada
y pasa a contradecir a lo que realmente esta sirviendo el cluster.

Ese desfase es justamente lo que la consigna 3.3.2 pide evitar. Este script lo
cierra: no recibe parametros ni supone nada, lee el registro y escribe lo que
encuentra.

Uso:
    python actualizar_ficha.py

Correr siempre despues de mover el alias de despliegue.
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone

import mlflow

import config as cfg


def obtener_metrica(metricas: dict, nombre: str) -> str:
    valor = metricas.get(nombre)
    return f"{valor:.4f}" if valor is not None else "n/d"


def main() -> int:
    cfg.configurar_mlflow()
    cliente = mlflow.MlflowClient()

    try:
        version = cliente.get_model_version_by_alias(
            cfg.REGISTERED_MODEL_NAME, cfg.DEPLOYMENT_ALIAS
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: no se pudo leer el alias '{cfg.DEPLOYMENT_ALIAS}' de "
              f"'{cfg.REGISTERED_MODEL_NAME}': {exc}", file=sys.stderr)
        return 1

    run = cliente.get_run(version.run_id)
    metricas = run.data.metrics
    parametros = run.data.params

    nombre_corrida = run.data.tags.get("mlflow.runName", "(sin nombre)")
    hiperparams = ", ".join(
        f"{k}={v}" for k, v in sorted(parametros.items())
        if k in {"alpha", "C", "n_estimators", "max_depth", "learning_rate", "min_samples_leaf"}
    ) or "(sin hiperparametros registrados)"

    ficha = cfg.RAIZ / "MODELO_DESPLEGADO.md"
    ficha.write_text(f"""# Modelo desplegado

> Generado automaticamente por `src/actualizar_ficha.py` a partir del Model
> Registry. No editar a mano.

| Campo | Valor |
|---|---|
| Nombre registrado | `{cfg.REGISTERED_MODEL_NAME}` |
| Version | **{version.version}** |
| Alias de despliegue | `{cfg.DEPLOYMENT_ALIAS}` |
| Run de origen | `{version.run_id}` |
| Experimento | `{cfg.MLFLOW_EXPERIMENT_NAME}` |
| Corrida ganadora | `{nombre_corrida}` |
| Hiperparametros | {hiperparams} |
| {cfg.METRICA_PRINCIPAL} (criterio de seleccion) | {obtener_metrica(metricas, cfg.METRICA_PRINCIPAL)} |
| Exactitud balanceada en test | {obtener_metrica(metricas, 'exactitud_balanceada')} |
| ROC AUC en test | {obtener_metrica(metricas, 'roc_auc')} |
| Datos hasta | {parametros.get('fecha_corte', 'n/d')} |
| Filas train / test | {parametros.get('n_train', '?')} / {parametros.get('n_test', '?')} |
| Semilla | {parametros.get('semilla', cfg.RANDOM_SEED)} |
| Ficha actualizada el | {datetime.now(timezone.utc).isoformat(timespec='seconds')} |
| Python | {platform.python_version()} |

## Descripcion registrada

{version.description or '(sin descripcion)'}

---

El servicio de inferencia carga este modelo por la referencia
`models:/{cfg.REGISTERED_MODEL_NAME}@{cfg.DEPLOYMENT_ALIAS}`, nunca por una ruta
de archivo. Mover el alias a otra version, reconstruir la imagen y reiniciar el
despliegue es todo lo que hace falta para cambiar el modelo en produccion.
""", encoding="utf-8")

    print(f"Ficha actualizada: {cfg.REGISTERED_MODEL_NAME} "
          f"v{version.version} (alias {cfg.DEPLOYMENT_ALIAS}, run {version.run_id})")
    print(f"Escrita en {ficha.relative_to(cfg.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
