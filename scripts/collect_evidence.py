"""Collect real tool responses. No sample successes are generated."""
import json
from datetime import datetime, timezone
from pathlib import Path

from agent.orchestrator import Orchestrator

PROMPTS = [
    "Which dataset version is currently tracked?",
    "Compare the last five training runs and recommend the best model based on F1.",
    "Report the training pipeline status and failed tasks.",
    "Why is my prediction API unavailable? Check deployment health.",
    "Find the best recent model, identify the dataset version used to train it, "
    "check deployment status, and explain whether retraining is necessary.",
]


def main():
    out = Path("evidence/live")
    out.mkdir(parents=True, exist_ok=True)
    agent = Orchestrator()
    for i, prompt in enumerate(PROMPTS, 1):
        response = agent.chat(prompt)
        (out / f"conversation-{i}.json").write_text(json.dumps({
            "captured_at": datetime.now(timezone.utc).isoformat(), "prompt": prompt,
            **response.model_dump()}, indent=2), encoding="utf-8")
    print("Saved five conversations to evidence/live. Review errors before submission.")


if __name__ == "__main__":
    main()
