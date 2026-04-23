FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY apps/api/README.md /app/README.md
COPY apps/api/pyproject.toml /app/pyproject.toml
COPY apps/api/src /app/src
COPY apps/api/agents /app/agents
COPY apps/api/docs /app/docs

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/data /app/logs

EXPOSE 8000

CMD ["uvicorn", "ndi_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
