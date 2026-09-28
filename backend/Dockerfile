FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY pytest.ini ./
COPY tests ./tests

RUN useradd --create-home appuser && mkdir -p /app/models_store && chown -R appuser /app
USER appuser

# Local/Docker image (production runs on Vercel, not this image). PORT defaults to 8000.
# One worker keeps local runs simple; CSV validation tokens are stored in PostgreSQL.
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health').status == 200 else 1)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
