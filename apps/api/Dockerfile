FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

# uv: gestor de dependencias rapido
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# Instala dependencias primero para aprovechar la cache de Docker
COPY pyproject.toml ./
RUN uv venv && uv pip install -e ".[dev]"

# Copia el resto del codigo
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "fitapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
