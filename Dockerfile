FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

COPY backend/requirements-runtime-lock.txt /app/backend/requirements-runtime-lock.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements-runtime-lock.txt

COPY backend/__init__.py /app/backend/__init__.py
COPY backend/app /app/backend/app
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/migrations /app/backend/migrations
COPY frontend /app/frontend
COPY data/seed /app/data/seed
COPY data/knowledge_base /app/data/knowledge_base

RUN mkdir -p /app/data/private/scans \
    && useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app/data

USER appuser
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
