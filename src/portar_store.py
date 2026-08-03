"""
Reescribe las rutas absolutas del store de MLflow para que funcione en otra
maquina o dentro de un contenedor.

El problema que resuelve
------------------------
MLflow guarda en su base de datos la ruta ABSOLUTA de cada artefacto. Si
entrenas en /home/tu-usuario/proyecto/mlflow_store y copias esa carpeta a
/app/mlflow_store dentro de una imagen de Docker, la base de datos sigue
apuntando a /home/tu-usuario/..., que no existe en el contenedor, y el
servicio falla al cargar el modelo.

La salida facil seria reentrenar dentro del build de la imagen. Pero eso
genera un run_id NUEVO, distinto del que muestras en `mlflow ui` durante la
defensa: se rompe justamente la trazabilidad que pide la consigna 3.3.2
(que el modelo servido corresponda al experimento exacto que lo produjo).

Este script hace lo correcto: copia el store tal cual, con su run_id
original, y solo reescribe el prefijo de las rutas. Son cuatro columnas en la
base de datos sqlite. El modelo que responde en Kubernetes es literalmente el
mismo run que se ve en la interfaz de MLflow.

Uso:
    python portar_store.py --nuevo-prefijo /app/mlflow_store
    python portar_store.py --nuevo-prefijo /app/mlflow_store --solo-mostrar
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# (tabla, columna) que contienen rutas absolutas de artefactos.
COLUMNAS_CON_RUTAS = [
    ("experiments", "artifact_location"),
    ("runs", "artifact_uri"),
    ("logged_models", "artifact_location"),
    ("model_versions", "storage_location"),
    ("model_versions", "source"),
]


def detectar_prefijo_actual(conexion: sqlite3.Connection) -> str | None:
    """
    Deduce el prefijo viejo mirando cualquier artifact_location registrado.

    Se toma el tramo anterior a '/mlartifacts', que es el nombre de carpeta
    que usa config.ARTIFACT_ROOT.
    """
    fila = conexion.execute(
        "SELECT artifact_location FROM experiments "
        "WHERE artifact_location LIKE '%/mlartifacts%' LIMIT 1"
    ).fetchone()
    return fila[0].split("/mlartifacts")[0] if fila else None


def portar(ruta_db: Path, nuevo_prefijo: str, solo_mostrar: bool = False) -> int:
    if not ruta_db.exists():
        print(f"ERROR: no existe la base de datos {ruta_db}", file=sys.stderr)
        return 1

    conexion = sqlite3.connect(ruta_db)
    viejo = detectar_prefijo_actual(conexion)

    if viejo is None:
        print("No se encontraron rutas de artefactos que reescribir.")
        return 0

    nuevo = nuevo_prefijo.rstrip("/")
    print(f"Prefijo actual : {viejo}")
    print(f"Prefijo nuevo  : {nuevo}")

    if viejo == nuevo:
        print("Ya coinciden, no hay nada que hacer.")
        return 0

    if solo_mostrar:
        print("\n(--solo-mostrar: no se modifico nada)")
        return 0

    total = 0
    for tabla, columna in COLUMNAS_CON_RUTAS:
        try:
            n = conexion.execute(
                f'UPDATE {tabla} SET "{columna}" = replace("{columna}", ?, ?) '
                f'WHERE "{columna}" LIKE ?',
                (viejo, nuevo, viejo + "%"),
            ).rowcount
            total += n
            print(f"  {tabla}.{columna}: {n} filas")
        except sqlite3.OperationalError:
            # La columna puede no existir segun la version de MLflow que
            # creo el esquema; no es un error.
            print(f"  {tabla}.{columna}: no existe en este esquema, se omite")

    conexion.commit()
    conexion.close()
    print(f"\nListo: {total} rutas reescritas.")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=None,
                   help="Ruta a mlflow.db (por defecto, el store del proyecto)")
    p.add_argument("--nuevo-prefijo", required=True,
                   help="Directorio donde vivira el store (ej. /app/mlflow_store)")
    p.add_argument("--solo-mostrar", action="store_true",
                   help="Mostrar que se cambiaria, sin modificar nada")
    args = p.parse_args()

    if args.db:
        ruta = Path(args.db)
    else:
        import config as cfg
        ruta = cfg.DIR_STORE / "mlflow.db"

    sys.exit(portar(ruta, args.nuevo_prefijo, args.solo_mostrar))
