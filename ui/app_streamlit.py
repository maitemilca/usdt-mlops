"""
Puntos extra -- Interfaz web que consume la API desplegada en Kubernetes.

La consigna es explicita: "que el consumo de la API sea real y funcione contra
el servicio desplegado en Kubernetes, no contra un proceso local".

Por eso esta interfaz es un cliente HTTP y nada mas. No importa el modelo, no
importa features.py, no calcula ninguna variable: todo lo que hace es armar un
JSON y mandarlo por `requests` al Service de la Fase 3. Si el clúster esta
apagado, la interfaz no puede predecir nada, y esa es justamente la prueba de
que no hay atajos.

Ejecutar:
    pip install -r ui/requirements.txt
    streamlit run ui/app_streamlit.py
"""
from __future__ import annotations

import collections
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

URL_POR_DEFECTO = "http://localhost:30080"   # NodePort del Service (k8s/service.yaml)
CSV_POR_DEFECTO = Path(__file__).resolve().parent.parent / "data" / "usdtbol_full.csv"
DIAS_MINIMOS = 31

st.set_page_config(page_title="TC USDT/BOB - Predictor", page_icon=None, layout="wide")


# --------------------------------------------------------------------------
# Cliente HTTP
# --------------------------------------------------------------------------
def pedir(url: str, ruta: str, metodo: str = "GET", cuerpo: dict | None = None):
    """Llama a la API y devuelve (ok, contenido)."""
    try:
        if metodo == "POST":
            respuesta = requests.post(f"{url}{ruta}", json=cuerpo, timeout=10)
        else:
            respuesta = requests.get(f"{url}{ruta}", timeout=10)
        return respuesta.ok, respuesta.json()
    except requests.exceptions.RequestException as exc:
        return False, {"error": str(exc)}


@st.cache_data(show_spinner=False)
def cargar_historial(ruta: Path) -> pd.DataFrame:
    """
    Serie diaria a partir del CSV crudo.

    Ojo: este promedio diario es solo para ARMAR el cuerpo de la peticion. El
    calculo de las variables del modelo lo hace el servicio, no la interfaz.
    """
    crudo = pd.read_csv(ruta)
    crudo.columns = ["fecha", "precio"]
    crudo["fecha"] = pd.to_datetime(crudo["fecha"])
    diario = crudo.set_index("fecha")["precio"].resample("D").mean().ffill()
    return diario.reset_index()


# --------------------------------------------------------------------------
# Barra lateral: conexion y diagnostico
# --------------------------------------------------------------------------
st.sidebar.title("Servicio")
url_api = st.sidebar.text_input("URL de la API", value=URL_POR_DEFECTO).rstrip("/")
st.sidebar.caption("Es el NodePort del Service de Kubernetes, no un proceso local.")

if st.sidebar.button("Comprobar estado", use_container_width=True):
    ok, datos = pedir(url_api, "/health")
    if ok:
        st.sidebar.success(f"Responde el pod: {datos.get('served_by_pod')}")
    else:
        st.sidebar.error(f"Sin respuesta: {datos.get('error', datos)}")

if st.sidebar.button("Ver modelo desplegado", use_container_width=True):
    ok, datos = pedir(url_api, "/model-info")
    if ok:
        st.sidebar.json(datos)
    else:
        st.sidebar.error(f"Sin respuesta: {datos.get('error', datos)}")

st.sidebar.divider()
st.sidebar.subheader("Balanceo de carga")
st.sidebar.caption("Repite la demostracion 2 de la Fase 3 desde la interfaz.")
n_peticiones = st.sidebar.slider("Peticiones a enviar", 5, 40, 20)

if st.sidebar.button("Lanzar peticiones", use_container_width=True):
    conteo = collections.Counter()
    barra = st.sidebar.progress(0.0)
    for i in range(n_peticiones):
        ok, datos = pedir(url_api, "/health")
        conteo[datos.get("served_by_pod", "sin respuesta") if ok else "error"] += 1
        barra.progress((i + 1) / n_peticiones)
    barra.empty()
    st.sidebar.write(f"**{len(conteo)} pod(s) respondieron:**")
    for pod, veces in conteo.most_common():
        st.sidebar.write(f"- `{pod}`: {veces}")


# --------------------------------------------------------------------------
# Cuerpo principal
# --------------------------------------------------------------------------
st.title("Prediccion del tipo de cambio USDT/BOB")
st.caption(
    "El modelo responde si el dolar paralelo sube manana. Esta pagina no "
    "calcula nada: consulta el servicio desplegado en Kubernetes."
)

st.subheader("1. Historial a enviar")
origen = st.radio(
    "Origen de los datos",
    ["Serie del proyecto", "Subir un CSV propio"],
    horizontal=True,
    label_visibility="collapsed",
)

historial = None
if origen == "Serie del proyecto":
    if CSV_POR_DEFECTO.exists():
        historial = cargar_historial(CSV_POR_DEFECTO)
        st.caption(f"Fuente: `data/{CSV_POR_DEFECTO.name}`")
    else:
        st.error(f"No se encontro {CSV_POR_DEFECTO}")
else:
    subido = st.file_uploader("CSV con dos columnas: fecha y precio", type="csv")
    if subido is not None:
        historial = cargar_historial(subido)

if historial is not None:
    dias = st.slider(
        "Dias de historial a enviar", DIAS_MINIMOS, min(180, len(historial)),
        min(60, len(historial)),
        help=f"El servicio exige al menos {DIAS_MINIMOS} dias para calcular la "
             "desviacion contra la media de 30 dias.",
    )
    ventana = historial.tail(dias)

    izquierda, derecha = st.columns([2, 1])
    with izquierda:
        st.line_chart(ventana.set_index("fecha")["precio"], height=260)
    with derecha:
        st.metric("Ultimo dia", ventana["fecha"].iloc[-1].strftime("%Y-%m-%d"))
        st.metric("Ultimo precio", f"{ventana['precio'].iloc[-1]:.2f} Bs")
        st.metric("Dias enviados", len(ventana))

    st.subheader("2. Prediccion")
    if st.button("Consultar al servicio", type="primary", use_container_width=True):
        cuerpo = {
            "historial": [
                {"fecha": f.strftime("%Y-%m-%d"), "precio": round(float(p), 4)}
                for f, p in zip(ventana["fecha"], ventana["precio"])
            ]
        }
        with st.spinner("Consultando la API en Kubernetes..."):
            ok, datos = pedir(url_api, "/predict", metodo="POST", cuerpo=cuerpo)

        if not ok:
            st.error(f"El servicio no respondio: {datos.get('error', datos)}")
            st.info(
                "Comproba que el despliegue este arriba:\n\n"
                "```\nkubectl get pods -l app=tc-usdt-api\n```"
            )
        else:
            sube = datos["clase"] == 1
            c1, c2, c3 = st.columns(3)
            c1.metric(f"Prediccion para {datos['fecha_predicha']}", datos["direccion"])
            probabilidad = datos.get("probabilidad_sube")
            c2.metric("Probabilidad de subida",
                      f"{probabilidad:.1%}" if probabilidad is not None else "n/d")
            c3.metric("Precio de referencia", f"{datos['precio_referencia']:.2f} Bs")

            (st.warning if sube else st.info)(
                f"El modelo estima que el tipo de cambio **{datos['direccion'].lower()}** "
                f"el {datos['fecha_predicha']}."
            )

            st.caption(
                f"Respondio el pod `{datos['served_by_pod']}` — modelo "
                f"`{datos['model_alias']}` version {datos['model_version']} "
                f"(run `{datos['run_id'][:12]}...`)"
            )
            with st.expander("Respuesta completa de la API"):
                st.json(datos)

st.divider()
st.caption(
    "Proyecto final del modulo MLOps y puesta en produccion — "
    "Maestria en Ciencia de Datos e IA, UAGRM."
)
