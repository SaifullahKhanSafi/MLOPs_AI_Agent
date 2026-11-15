import json
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from agent.config import settings
from agent.orchestrator import Orchestrator
from agent.schemas import ChatRequest, ChatResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
agent = Orchestrator()
state = {"model": None, "metadata": {}}


@asynccontextmanager
async def lifespan(app):
    path = Path(settings.model_path)
    if path.exists():
        state["model"] = joblib.load(path)
        metadata = path.with_name("model_metadata.json")
        if metadata.exists():
            state["metadata"] = json.loads(metadata.read_text())
    yield


app = FastAPI(title="MLOps AI Agent & Iris Inference", version="1.0.0", lifespan=lifespan)


def authenticate(x_api_key: str = Header(default="")):
    if not settings.agent_api_key or not secrets.compare_digest(x_api_key, settings.agent_api_key):
        raise HTTPException(401, "Valid X-API-Key required; configure AGENT_API_KEY")


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    if state["model"] is None:
        raise HTTPException(503, "No quality-gated model is loaded")
    return {"status": "ready", "model": state["metadata"]}


class PredictionRequest(BaseModel):
    instances: list[list[float]] = Field(min_length=1, max_length=100)


@app.post("/predict")
def predict(request: PredictionRequest):
    if state["model"] is None:
        raise HTTPException(503, "No model loaded")
    if any(len(row) != 4 for row in request.instances):
        raise HTTPException(422, "Each instance requires four Iris features")
    values = np.asarray(request.instances)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise HTTPException(422, "Features must be positive finite numbers")
    return {"predictions": state["model"].predict(values).tolist(), "model": state["metadata"]}


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(authenticate)])
def chat(request: ChatRequest):
    try:
        return agent.chat(request.message, request.confirmation_token)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(502, "Agent provider unavailable; no operational results verified") from None
