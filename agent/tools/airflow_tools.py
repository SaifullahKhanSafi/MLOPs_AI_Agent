from urllib.parse import quote

import httpx

from agent.config import settings


def request(method: str, path: str, body: dict | None = None) -> dict:
    with httpx.Client(timeout=settings.tool_timeout) as c:
        response = c.post(f"{settings.airflow_url}/auth/token", json={
            "username": settings.airflow_username, "password": settings.airflow_password})
        response.raise_for_status()
        token = response.json()["access_token"]
        response = c.request(method, f"{settings.airflow_url}/api/v2/{path}",
                             headers={"Authorization": f"Bearer {token}"}, json=body)
        response.raise_for_status()
        return response.json()


def dag_path(dag_id: str) -> str:
    if dag_id != settings.approved_dag:
        raise PermissionError("DAG is outside the approved allowlist")
    return "dags/" + quote(dag_id, safe="")


def list_dags() -> dict:
    return request("GET", "dags?limit=100")


def dag_runs(dag_id: str = "training_pipeline") -> dict:
    # Manually triggered Airflow 3 runs may have null logical_date.
    return request("GET", dag_path(dag_id) + "/dagRuns?limit=10&order_by=-run_after")


def dag_run(dag_id: str, run_id: str) -> dict:
    return request("GET", dag_path(dag_id) + "/dagRuns/" + quote(run_id, safe=""))


def task_instances(dag_id: str, run_id: str) -> dict:
    return request("GET", dag_path(dag_id) + "/dagRuns/" + quote(run_id, safe="")
                   + "/taskInstances")


def task_logs(dag_id: str, run_id: str, task_id: str, try_number: int = 1) -> dict:
    if not 1 <= try_number <= 20:
        raise ValueError("Invalid try number")
    return request("GET", dag_path(dag_id) + "/dagRuns/" + quote(run_id, safe="")
                   + "/taskInstances/" + quote(task_id, safe="")
                   + f"/logs/{try_number}?full_content=true")


def trigger_dag(dag_id: str = "training_pipeline", conf: dict | None = None) -> dict:
    conf = conf or {}
    if set(conf) - {"fail_validation", "force_quality_failure"} or any(
            not isinstance(value, bool) for value in conf.values()):
        raise ValueError("Only boolean failure-demo flags are supported in DAG configuration")
    return request("POST", dag_path(dag_id) + "/dagRuns", {"logical_date": None,
                                                          "conf": conf})
