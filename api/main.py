import logging
import secrets

from fastapi import Depends, Header, HTTPException

from agent.config import settings
from agent.orchestrator import Orchestrator
from agent.schemas import ChatRequest, ChatResponse
from api.inference import app

logging.basicConfig(level=logging.INFO, format="%(message)s")
agent = Orchestrator()
app.title = "MLOps AI Agent & Iris Inference"


def authenticate(x_api_key: str = Header(default="")):
    if not settings.agent_api_key or not secrets.compare_digest(x_api_key, settings.agent_api_key):
        raise HTTPException(401, "Valid X-API-Key required; configure AGENT_API_KEY")


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
