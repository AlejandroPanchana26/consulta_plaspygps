# ============================================================================
# Plaspy - Consulta de flota (Streamlit)
# Interfaz web: ingresa userName + apiKey y consulta deviceId, placa y
# fecha/hora del último reporte de cada vehículo.
# ============================================================================
import re
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://api.plaspy.com"
HTTP_TIMEOUT = 20
PATRON_PLACA = re.compile(r"[A-Z]{3}\d{2,3}[A-Z]?", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Capa de acceso a la API de Plaspy
# ----------------------------------------------------------------------------
def get_token(user_name: str, api_key: str):
    """Autentica y devuelve (token, error). token=None si falla."""
    try:
        r = requests.post(
            f"{BASE_URL}/api/Auth/Token",
            json={"userName": user_name, "apiKey": api_key},
            headers={"Content-Type": "application/json"},
            timeout=HTTP_TIMEOUT,
        )
        data = r.json()
    except Exception as e:
        return None, f"Error de red: {e}"
    if not data.get("success"):
        return None, data.get("error", "Autenticación fallida")
    return data.get("token"), None


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def list_devices(token: str) -> list:
    try:
        r = requests.get(f"{BASE_URL}/api/devices",
                         headers=_headers(token), timeout=HTTP_TIMEOUT)
        data = r.json()
    except Exception:
        return []
    if isinstance(data, list):
        return data
    return data.get("devices") or data.get("data") or []


def get_device_detail(token: str, device_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/api/devices/{device_id}",
                         headers=_headers(token), timeout=HTTP_TIMEOUT)
        return r.json()
    except Exception:
        return {}


def get_last_location(token: str, device_id: str):
    try:
        r = requests.get(f"{BASE_URL}/api/devices/{device_id}/lastLocation",
                         headers=_headers(token), timeout=HTTP_TIMEOUT)
        data = r.json()
    except Exception:
        return None
    if not data.get("success"):
        return None
    return data.get("lastLocation") or {}


# ----------------------------------------------------------------------------
# Utilidades de negocio
# ----------------------------------------------------------------------------
def extraer_placa(dev: dict, detalle: dict, preferir: str):
    """Devuelve (placa, fuente). 'preferir' = 'name' o 'description'."""
    d = {}
    if isinstance(detalle, dict):
        d = detalle.get("device") or detalle.get("data") or detalle
    name = (dev.get("name") or d.get("name") or "").strip()
    desc = (d.get("description") or "").strip()

    orden = [("name", name), ("description", desc)]
    if preferir == "description":
        orden = [("description", desc), ("name", name)]

    for fuente, valor in orden:
        if valor:
            m = PATRON_PLACA.search(valor)
            if m:
                return m.group().upper(), fuente

    limpio = re.sub(r"^(CARRO|MOTO|MINIVAN|TURBO|BUS|CAMION)\s+", "",
                    name, flags=re.IGNORECASE)
    return (limpio or desc or "(sin placa)"), "sin patrón"


def formatear_fecha(iso_str):
    if not iso_str:
        return "(sin datos)", None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S"), dt
    except Exception:
        return iso_str, None


def clasificar_pulso(loc: dict) -> str:
    if not loc:
        return "—"
    for campo in ("alerts", "warnings"):
        if loc.get(campo):
            return "EVENTO"
    return "POSICIÓN"


def consultar_cuenta(user_name: str, api_key: str, preferir_placa: str,
                     incluir_pulso: bool, progreso=None):
    """Orquesta la consulta completa de una cuenta. Devuelve (df, error)."""
    token, err = get_token(user_name, api_key)
    if err:
        return None, err

    devices = list_devices(token)
    filas = []
    total = len(devices) or 1

    for i, dev in enumerate(devices):
        device_id = dev.get("id") or dev.get("deviceId")
        if not device_id:
            continue

        detalle = get_device_detail(token, device_id)
        placa, fuente = extraer_placa(dev, detalle, preferir_placa)

        fila = {
            "deviceId": device_id,
            "placa": placa,
            "vehiculo": dev.get("name", ""),
            "fuente_placa": fuente,
        }

        if incluir_pulso:
            loc = get_last_location(token, device_id)
            fecha_txt, _ = formatear_fecha(loc.get("dateTime") if loc else None)
            fila["ultimo_reporte"] = fecha_txt
            fila["tipo"] = clasificar_pulso(loc)

        filas.append(fila)

        if progreso is not None:
            progreso.progress((i + 1) / total,
                              text=f"Consultando {i + 1}/{len(devices)} dispositivos…")

    if not filas:
        return pd.DataFrame(), None
    return pd.DataFrame(filas), None


# ----------------------------------------------------------------------------
# Interfaz Streamlit
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Consulta de flota · Plaspy",
                   page_icon="🚗", layout="wide")

# --- Estilos ligeros ---
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; max-width: 1200px; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🚗 Consulta de flota · Plaspy")
st.caption("Consulta deviceId, placa y último reporte de tus vehículos GPS.")

# --- Panel lateral: credenciales y opciones ---
with st.sidebar:
    st.header("🔐 Credenciales")
    st.caption("La API de Plaspy usa **userName + apiKey** (no la contraseña). "
               "La apiKey se genera en Mi Cuenta → Clave API.")
    user_name = st.text_input("userName", placeholder="usuario o email")
    api_key = st.text_input("apiKey", type="password",
                            placeholder="clave generada en Plaspy")

    st.divider()
    st.header("⚙️ Opciones")
    incluir_pulso = st.toggle("Incluir último reporte (fecha/hora)", value=True,
                              help="Consulta lastLocation por cada dispositivo. "
                                   "Un poco más lento en flotas grandes.")
    preferir_placa = st.radio(
        "¿Dónde está la placa?",
        options=["name", "description"],
        format_func=lambda x: "Campo 'name' (ej. CARRO FXS493)"
                    if x == "name" else "Campo 'description'",
        help="Elige de qué campo extraer la placa según cómo la tengas cargada.",
    )
    consultar = st.button("🔍 Consultar", type="primary", use_container_width=True)

# --- Cuerpo principal ---
if consultar:
    if not user_name or not api_key:
        st.warning("Ingresa userName y apiKey en el panel lateral.")
        st.stop()

    barra = st.progress(0.0, text="Autenticando…")
    with st.spinner("Consultando la API de Plaspy…"):
        df, error = consultar_cuenta(user_name, api_key, preferir_placa,
                                     incluir_pulso, progreso=barra)
    barra.empty()

    if error:
        st.error(f"No se pudo consultar: **{error}**")
        st.info("Verifica que la apiKey sea la generada en Plaspy (no la "
                "contraseña) y que el userName sea correcto.")
        st.stop()

    if df is None or df.empty:
        st.info("La cuenta no tiene dispositivos o no devolvió datos.")
        st.stop()

    # Guardar en sesión para permitir filtrar/descargar sin re-consultar
    st.session_state["df"] = df
    st.session_state["hora_consulta"] = datetime.now(timezone.utc)

# --- Mostrar resultados (desde sesión) ---
if "df" in st.session_state:
    df = st.session_state["df"].copy()
    hora = st.session_state.get("hora_consulta")

    # Métricas resumen
    c1, c2, c3 = st.columns(3)
    c1.metric("Vehículos", len(df))
    if "ultimo_reporte" in df.columns:
        sin_datos = (df["ultimo_reporte"] == "(sin datos)").sum()
        c2.metric("Sin reporte", int(sin_datos))
        eventos = (df.get("tipo") == "EVENTO").sum() if "tipo" in df else 0
        c3.metric("Con evento activo", int(eventos))

    if hora:
        st.caption(f"Última consulta: {hora.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # Filtro por placa/vehículo
    filtro = st.text_input("🔎 Filtrar por placa o vehículo", "")
    if filtro:
        mask = (df["placa"].str.contains(filtro, case=False, na=False) |
                df["vehiculo"].str.contains(filtro, case=False, na=False))
        df = df[mask]

    # Ordenar por último reporte si existe
    if "ultimo_reporte" in df.columns:
        df["_orden"] = pd.to_datetime(df["ultimo_reporte"], errors="coerce")
        df = df.sort_values("_orden", ascending=False, na_position="last")
        df = df.drop(columns=["_orden"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Descarga CSV
    csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇️ Descargar CSV", data=csv,
                       file_name="plaspy_flota.csv", mime="text/csv")
else:
    st.info("👈 Ingresa tus credenciales en el panel lateral y pulsa "
            "**Consultar** para ver tu flota.")
