FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY scripts/init_db.py ./scripts/init_db.py
COPY web/ ./web/

EXPOSE 8000

# Apply (idempotent) schema, then serve.
CMD ["sh", "-c", "python scripts/init_db.py && exec uvicorn loremaster.api:app --host 0.0.0.0 --port 8000"]
