FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODEL_PATH=/app/artifacts/model.joblib
WORKDIR /app
COPY requirements-inference.txt ./
RUN pip install --no-cache-dir -r requirements-inference.txt && useradd --uid 10001 --create-home appuser
COPY agent/__init__.py agent/config.py ./agent/
COPY api/__init__.py api/inference.py ./api/
COPY --chown=10001:10001 artifacts/model.joblib artifacts/model_metadata.json ./artifacts/
USER 10001
EXPOSE 8000
CMD ["uvicorn", "api.inference:app", "--host", "0.0.0.0", "--port", "8000"]
