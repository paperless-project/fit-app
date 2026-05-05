FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# uv: gestor de dependencias rapido
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# Instala dependencias en /opt/venv para que no quede bajo /app
# y no sea sobreescrito por el volumen de desarrollo
COPY pyproject.toml ./
RUN uv venv /opt/venv && uv pip install --python /opt/venv -e ".[dev]"

# Copia el resto del codigo
COPY . .

EXPOSE 8000

CMD ["uvicorn", "fitapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
