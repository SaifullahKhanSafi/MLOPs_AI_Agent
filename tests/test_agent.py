import json
import logging
import subprocess
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from agent.config import settings
from agent.orchestrator import Orchestrator
from agent.registry import Registry, redact
from agent.tools import airflow_tools as af
from agent.tools import dvc_tools as dv
from agent.tools import kubernetes_tools as ku
from agent.tools import mlflow_tools as mf
from api.main import app, state


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "rules")
    monkeypatch.setattr(settings, "agent_api_key", "test-secret")
    monkeypatch.setattr(settings, "approved_namespace", "mlops-agent")


def fake_registry(payloads=None):
    reg = Registry()
    for name in reg.functions:
        value = (payloads or {}).get(name, {})
        reg.functions[name] = lambda value=value, **kwargs: value
    return reg


def test_mandatory_scenario_queries_four_integrations_without_mutation():
    agent = Orchestrator(fake_registry())
    response = agent.chat("Find the best recent model, dataset version, deployment, and retraining need")
    names = {e.tool for e in response.evidence}
    assert {"mlflow_best", "dvc_version", "dvc_status", "k8s_workloads", "airflow_runs"} <= names
    assert not names & {"airflow_trigger", "k8s_restart"}
    assert response.proposed_action is None


def test_selection_uses_recorded_commit_for_dataset():
    reg = fake_registry({"mlflow_best": {"best": {"run_id": "run1", "metrics": {"f1": .95},
                                                "tags": {"git_commit": "abc123"}}}})
    seen = []
    reg.functions["dvc_version"] = lambda rev="HEAD": seen.append(rev) or {"git_commit": rev}
    response = Orchestrator(reg).chat("Find the best model")
    assert seen == ["abc123"]
    assert "run1" in response.answer


def test_service_failure_does_not_invent_results():
    reg = fake_registry()

    def fail(**kwargs):
        raise ConnectionError("password=secret-url")

    for name in reg.functions:
        reg.functions[name] = fail
    response = Orchestrator(reg).chat("Find the best recent model and check deployment")
    assert all(e.status == "error" for e in response.evidence)
    assert "No verified operational facts" in response.answer
    assert "secret-url" not in response.model_dump_json()
    assert "state is unknown" in response.answer


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("oops"), subprocess.TimeoutExpired("dvc", 1)])
def test_tool_timeout_reports_unknown_state(exc):
    reg = Registry()

    def fail():
        raise exc

    reg.functions["dvc_status"] = fail
    result = reg.execute("dvc_status", {}, "req")
    assert result.status == "error"
    assert "timed out" in result.error


def test_invalid_tool_and_extra_arguments_rejected():
    reg = Registry()
    assert reg.execute("shell", {"command": "whoami"}, "req").status == "error"
    assert reg.execute("dvc_status", {"command": "whoami"}, "req").status == "error"


def test_mutation_without_confirmation_is_denied():
    reg = fake_registry()
    assert reg.execute("k8s_restart", {"namespace": "mlops-agent"}, "req").status == "denied"
    assert reg.execute("airflow_trigger", {}, "req").status == "denied"
    assert reg.execute("k8s_restart", {"namespace": "mlops-agent", "confirmed": True},
                       "req").status == "error"


def test_confirmation_is_bound_to_action_and_single_use():
    reg = fake_registry()
    called = []
    reg.functions["k8s_restart"] = lambda **args: called.append(args) or {"accepted": True}
    agent = Orchestrator(reg)
    proposal = agent.chat("restart deployment")
    assert not called
    result = agent.chat("confirm", proposal.confirmation_token)
    assert result.evidence[0].status == "ok"
    assert called == [{"namespace": "mlops-agent", "confirmed": True}]
    with pytest.raises(PermissionError):
        agent.chat("confirm", proposal.confirmation_token)


def test_expired_confirmation_is_denied():
    agent = Orchestrator(fake_registry())
    proposal = agent.chat("trigger training")
    token = proposal.confirmation_token
    _, name, args = agent.pending[token]
    agent.pending[token] = (time.monotonic() - 1, name, args)
    with pytest.raises(PermissionError):
        agent.chat("confirm", token)


def test_namespace_and_dag_allowlist_block_modification():
    with pytest.raises(PermissionError):
        ku.restart_deployment("kube-system", confirmed=True)
    with pytest.raises(PermissionError):
        af.dag_path("delete_everything")


def test_airflow_authentication_and_v2_paths(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/auth/token":
            assert "username" in json.loads(request.content)
            return httpx.Response(200, json={"access_token": "jwt-test"})
        assert request.headers["Authorization"] == "Bearer jwt-test"
        return httpx.Response(200, json={"dag_runs": []})

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    monkeypatch.setattr(af.httpx, "Client", lambda **kw: original(transport=transport, **kw))
    assert af.dag_runs() == {"dag_runs": []}
    assert requests[1].url.path == "/api/v2/dags/training_pipeline/dagRuns"


def test_best_run_excludes_failed_missing_nan_and_handles_min(monkeypatch):
    runs = [
        {"run_id": "bad", "status": "FAILED", "metrics": {"f1": 1}},
        {"run_id": "good", "status": "FINISHED", "metrics": {"f1": .9}},
        {"run_id": "low", "status": "FINISHED", "metrics": {"f1": .7}},
        {"run_id": "nan", "status": "FINISHED", "metrics": {"f1": float("nan")}},
        {"run_id": "missing", "status": "FINISHED", "metrics": {}},
    ]
    monkeypatch.setattr(mf, "list_runs", lambda limit: {"runs": runs})
    assert mf.best_run()["best"]["run_id"] == "good"
    assert mf.best_run(direction="min")["best"]["run_id"] == "low"


def test_git_revision_injection_rejected():
    for value in ["--help", "HEAD; whoami", "$(whoami)", "HEAD:secret"]:
        with pytest.raises(ValueError):
            dv.dataset_version(value)


def test_logs_record_only_metadata_without_secrets(caplog):
    reg = fake_registry()
    with caplog.at_level(logging.INFO, logger="mlops.tools"):
        reg.execute("dvc_status", {}, "request-123")
    record = json.loads(caplog.records[-1].message)
    assert {"tool", "status", "duration_ms", "request_id"} == set(record)
    assert record["request_id"] == "request-123"
    assert "test-secret" not in caplog.text
    assert "test-secret" not in json.dumps(redact({"logs": "api_key=test-secret"}))


def test_chat_auth_and_invalid_requests():
    client = TestClient(app)
    assert client.post("/chat", json={"message": "best model"}).status_code == 401
    assert client.post("/chat", json={"message": ""},
                       headers={"X-API-Key": "test-secret"}).status_code == 422


def test_inference_readiness_and_feature_validation(monkeypatch):
    client = TestClient(app)
    monkeypatch.setitem(state, "model", None)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    monkeypatch.setitem(state, "model", SimpleNamespace(predict=lambda x: np_array([0])))
    assert client.post("/predict", json={"instances": [[1, 2]]}).status_code == 422
    assert client.post("/predict", json={"instances": [[5.1, 3.5, 1.4, .2]]}).json()[
        "predictions"] == [0]


def np_array(value):
    import numpy as np
    return np.array(value)


def test_failed_quality_gate_preserves_previously_promoted_model(tmp_path, monkeypatch):
    from training import train

    monkeypatch.setattr(train, "OUT", tmp_path)
    (tmp_path / "model.joblib").write_bytes(b"previous-good-model")
    (tmp_path / "candidate.joblib").write_bytes(b"bad-new-candidate")
    (tmp_path / "run.json").write_text(json.dumps({"run_id": "run1", "f1": .1}))
    tags = []
    monkeypatch.setattr(train.mlflow.tracking, "MlflowClient", lambda: SimpleNamespace(
        set_tag=lambda *args: tags.append(args)))
    with pytest.raises(ValueError, match="Quality gate failed"):
        train.quality_gate()
    assert (tmp_path / "model.joblib").read_bytes() == b"previous-good-model"
    assert tags == [("run1", "quality_gate", "failed")]


def test_llm_cannot_claim_success_when_all_tools_failed(monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")
    reg = fake_registry()
    reg.functions["k8s_workloads"] = lambda: (_ for _ in ()).throw(ConnectionError())
    replies = iter([
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call1", "type": "function",
         "function": {"name": "k8s_workloads", "arguments": "{}"}}]},
        {"role": "assistant", "content": "All pods healthy!"},
    ])
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json={"choices": [{"message": next(replies)}]}))
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=transport, **kw))
    response = Orchestrator(reg).chat("Check pods")
    assert "All pods healthy" not in response.answer
    assert "No verified operational facts" in response.answer
