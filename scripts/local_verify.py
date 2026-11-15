"""Verify actual trained-model inference and two local stage failures (not Airflow runs)."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from training.train import quality_gate, validate


def main():
    path = Path("artifacts/model.joblib")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    results = {"captured_at": datetime.now(timezone.utc).isoformat(),
               "scope": "Actual local stages and FastAPI inference; not Airflow or Kubernetes",
               "model": json.loads(Path("artifacts/model_metadata.json").read_text())}
    with TestClient(app) as client:
        health = client.get("/health/ready")
        prediction = client.post("/predict", json={"instances": [[5.1, 3.5, 1.4, .2]]})
        assert health.status_code == prediction.status_code == 200
        assert prediction.json()["predictions"] == [0]
        results["readiness"] = health.json()
        results["prediction"] = prediction.json()
    try:
        validate(fail_validation=True)
    except ValueError as exc:
        results["validation_failure"] = {"observed_error": str(exc),
                                         "resolution": "Remove injected flag"}
    else:
        raise AssertionError("Validation injection did not fail")
    try:
        quality_gate(force_quality_failure=True)
    except ValueError as exc:
        results["quality_failure"] = {"observed_error": str(exc),
                                      "promoted_model_preserved":
                                      hashlib.sha256(path.read_bytes()).hexdigest() == before}
    else:
        raise AssertionError("Quality injection did not fail")
    assert results["quality_failure"]["promoted_model_preserved"]
    quality_gate()  # Recover the run tag and preserve a valid promoted model.
    results["recovery"] = json.loads(Path("artifacts/model_metadata.json").read_text())
    target = Path("evidence/submission/local-verification.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Actual local verification saved to {target}")


if __name__ == "__main__":
    main()
