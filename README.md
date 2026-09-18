# Consulta de flota · Plaspy (Streamlit)

Interfaz web para consultar tu flota GPS en Plaspy. Ingresas **userName** y
**apiKey** y obtienes, por cada vehículo: **deviceId**, **placa** y
**fecha/hora del último reporte**.

## ¿Qué hace?

- Autentica contra la API de Plaspy (`POST /api/Auth/Token`) y obtiene el token JWT.
- Lista los dispositivos de la cuenta (`GET /api/devices`).
- Extrae la placa desde el nombre o la descripción del dispositivo.
- Opcionalmente consulta el último reporte de cada uno
  (`GET /api/devices/{deviceId}/lastLocation`) para mostrar fecha/hora.
- Muestra todo en una tabla filtrable y permite descargar el CSV.

---

## 1. Ejecución local

Requisitos: Python 3.9 o superior.

```bash
# 1. (Opcional) crea un entorno virtual
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate

# 2. Instala dependencias
pip install -r requirements.txt

# 3. Ejecuta la aplicación
streamlit run app.py
```

Se abrirá automáticamente en el navegador (por defecto http://localhost:8501).
Ingresa tus credenciales en el panel lateral y pulsa **Consultar**.

---

## 2. Credenciales

- **userName**: tu usuario de Plaspy (puede ser el email o el nombre de usuario).
- **apiKey**: la clave que se genera en el panel de Plaspy en
  **Mi Cuenta → Información de la cuenta → Clave API → Generar**.
  No es la contraseña de la plataforma.

> Al regenerar la apiKey en Plaspy, la anterior queda invalidada.

---

## 3. Despliegue en la nube

### Opción A — Streamlit Community Cloud (la más simple, gratis)

1. Sube este proyecto a un repositorio de GitHub (`app.py` + `requirements.txt`).
2. Entra a https://share.streamlit.io, conecta el repo y selecciona `app.py`.
3. La app queda publicada con una URL pública. Las credenciales las ingresa
   cada usuario en la interfaz (no se guardan en el código).

### Opción B — Docker (portátil a cualquier nube: AWS, Azure, GCP)

Crea un `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

Construir y ejecutar:

```bash
docker build -t plaspy-flota .
docker run -p 8501:8501 plaspy-flota
```

Esta imagen se puede desplegar en:
- **AWS**: App Runner, ECS/Fargate o Elastic Beanstalk.
- **Azure**: Azure Container Apps o App Service (contenedor).
- **GCP**: Cloud Run (recomendado; escala a cero y es muy económico).

Ejemplo Cloud Run:

```bash
gcloud run deploy plaspy-flota --source . \
    --region us-central1 --allow-unauthenticated --port 8501
```

---

## 4. Notas de seguridad

- Las credenciales se ingresan en la interfaz y se usan solo en memoria para la
  consulta; no se escriben en disco.
- Si publicas la app en una URL pública, considera restringir el acceso
  (autenticación de la plataforma, VPN, o Cloud Run con autenticación).
- Respeta los límites de la API de Plaspy (solicitudes por minuto y resultados
  diarios por dispositivo). En flotas grandes, desactiva "Incluir último
  reporte" si solo necesitas deviceId y placa (hace una sola llamada por
  dispositivo en vez de dos).
