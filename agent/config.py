import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    repo_root: Path = Path(__file__).resolve().parents[1]
    agent_mode: str = "rules"
    agent_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment: str = "iris-classifier"
    airflow_url: str = "http://localhost:8080"
    airflow_username: str = "admin"
    airflow_password: str = ""
    approved_namespace: str = "mlops-agent"
    approved_dag: str = "training_pipeline"
    model_path: str = "artifacts/model.joblib"
    min_f1: float = 0.90
    max_model_age_days: int = 30
    tool_timeout: float = 20


settings = Settings()

# MLflow's emoji run links can fail on Windows consoles using cp1252.
# Run identifiers and tracking evidence are returned as structured data instead.
os.environ.setdefault("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", "true")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", str(int(settings.tool_timeout)))
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "0")
os.environ.setdefault("MLFLOW_ARTIFACT_UPLOAD_DOWNLOAD_TIMEOUT", str(int(settings.tool_timeout)))
