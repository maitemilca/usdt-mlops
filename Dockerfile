# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# --- Dependencias fijadas por versión  ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Código y dato de entrenamiento  ---
COPY src/ ./src/
COPY data/usdt_bs.csv ./data/usdt_bs.csv

ENV MLFLOW_TRACKING_URI=sqlite:////app/mlflow_store/mlflow.db
ENV PYTHONUNBUFFERED=1

# --- Entrenar y registrar el modelo DURANTE el build ---
# Se re-entrena dentro de la imagen (en vez de copiar la carpeta mlruns/
# generada en otra máquina) porque MLflow guarda rutas absolutas de los
# artefactos en su base de datos: si copiáramos el store de otro filesystem,
# esas rutas no resolverían dentro del contenedor. Al entrenar aquí, con la
# semilla fija de config.py y las mismas dependencias pineadas, el resultado
# (hiperparámetros y métricas) es idéntico al registrado en el `mlflow ui`
# local -- solo cambia el run_id, porque MLflow genera uno nuevo cada vez.
RUN mkdir -p /app/mlflow_store \
    && cd src \
    && python train.py --data ../data/usdt_bs.csv

WORKDIR /app/src
EXPOSE 8000

# El servicio de inferencia carga el modelo por referencia al Model
# Registry (models:/usdt-bob-ridge-1h@champion), nunca desde un .pkl suelto.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
