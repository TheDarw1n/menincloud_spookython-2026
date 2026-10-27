FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY data/ data/
USER app
EXPOSE 8000
# UN SOLO WORKER: el estado del mundo vive en memoria. Nunca usar --workers > 1.
# --timeout-keep-alive 75: mayor que el idle timeout del ALB (60 s); si uvicorn cierra antes una
#   conexion que el ALB reutiliza, el jurado ve 502 (cuenta como error de disponibilidad).
# --no-access-log: una linea por cada POST /paso (cientos por turno) costaria CPU y CloudWatch.
# --ws-max-size/--ws-max-queue: el mapa nunca envia datos por /ws; sin limite uvicorn aceptaba
#   mensajes de 16 MiB y encolaba 32 por conexion.
# --ws-per-message-deflate false: comprimir el estado (~40 KB) costaba ~1 ms de CPU por visor y
#   por mensaje (2 por turno): con 100 visores, ~200 ms por turno robados a la rafaga de /paso.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75", "--no-access-log", "--ws-max-size", "4096", "--ws-max-queue", "1", "--ws-per-message-deflate", "false"]
