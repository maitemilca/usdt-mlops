# syntax=docker/dockerfile:1
#
# Fase 2 -- Imagen del servicio de inferencia.
#
# Decision de diseno importante (preguntable en la defensa):
# la imagen COPIA el store de MLflow entrenado en la maquina de desarrollo y
# le reescribe las rutas, en vez de reentrenar durante el build.
#
# El camino facil habria sido correr `python train.py` dentro del build. Pero
# eso genera un run_id NUEVO, distinto del que se muestra en `mlflow ui`
# durante la presentacion: se rompe la trazabilidad que pide la consigna 3.3.2
# (que el modelo que sirve peticiones corresponda al experimento exacto que lo
# produjo). Copiando el store y reescribiendo las rutas con portar_store.py,
# el modelo que responde en Kubernetes es literalmente el mismo run que se ve
# en la interfaz de MLflow, con el mismo identificador.
#
# El detalle tecnico que obliga a reescribir: MLflow guarda rutas ABSOLUTAS de
# los artefactos en su base de datos. El store entrenado en
# /home/usuario/proyecto/mlflow_store no resuelve dentro del contenedor, donde
# vive en /app/mlflow_store. Son cuatro columnas en sqlite; portar_store.py
# las actualiza de forma determinista.

FROM python:3.12-slim

# Evita que Python escriba .pyc y fuerza salida sin buffer, para que los logs
# del contenedor aparezcan en `kubectl logs` en el momento, no al cerrar.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias van primero y en su propia capa: mientras requirements.txt
# no cambie, Docker reutiliza esta capa y no reinstala nada al reconstruir.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo de la aplicacion.
COPY src/ ./src/

# Store de MLflow con el modelo ya entrenado y registrado.
COPY mlflow_store/ ./mlflow_store/

# Reescritura de rutas: sin esto, el contenedor buscaria los artefactos en la
# ruta de la maquina de desarrollo y el arranque fallaria.
RUN python src/portar_store.py --db /app/mlflow_store/mlflow.db \
        --nuevo-prefijo /app/mlflow_store

ENV MLFLOW_TRACKING_URI=sqlite:////app/mlflow_store/mlflow.db

# El servicio corre como usuario sin privilegios: si alguien lograra ejecutar
# codigo dentro del contenedor, no seria root.
RUN useradd --create-home --uid 10001 servicio \
    && chown -R servicio:servicio /app

# Se declara el usuario por su UID NUMERICO, no por su nombre. Kubernetes, con
# runAsNonRoot activado, valida antes de arrancar que el usuario de la imagen
# no sea root; si el Dockerfile pone "USER servicio", el kubelet no puede
# resolver ese nombre a un UID y rechaza el contenedor con
# CreateContainerConfigError: "image has non-numeric user".
USER 10001

WORKDIR /app/src
EXPOSE 8000

# Comprobacion de salud a nivel de imagen. Kubernetes usa sus propias sondas
# (ver k8s/deployment.yaml), pero esto hace que `docker ps` muestre el estado
# real tambien cuando se prueba la imagen suelta.
HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# El servicio carga el modelo por referencia al Model Registry
# (models:/tc-usdt-bob-direccion@champion), nunca desde un archivo suelto.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
