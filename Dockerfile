FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODEL_PATH=/app/artifacts/model.joblib
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY agent ./agent
COPY api ./api
COPY training ./training
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home appuser
COPY --chown=10001:10001 artifacts/model.joblib artifacts/model_metadata.json ./artifacts/
USER 10001
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
