import math

from mlflow.tracking import MlflowClient

from agent.config import settings


def client():
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


def list_experiments() -> dict:
    return {"experiments": [{"id": e.experiment_id, "name": e.name}
                            for e in client().search_experiments(max_results=50)]}


def serialize(run) -> dict:
    return {"run_id": run.info.run_id, "status": run.info.status,
            "start_time": run.info.start_time, "metrics": dict(run.data.metrics),
            "params": dict(run.data.params), "tags": dict(run.data.tags)}


def list_runs(limit: int = 5) -> dict:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    c = client()
    exp = c.get_experiment_by_name(settings.mlflow_experiment)
    if exp is None:
        return {"runs": [], "reason": "Experiment has not been created"}
    return {"runs": [serialize(r) for r in c.search_runs(
        [exp.experiment_id], max_results=limit, order_by=["attributes.start_time DESC"])]}


def run_details(run_id: str) -> dict:
    c = client()
    result = serialize(c.get_run(run_id))
    result["artifacts"] = [a.path for a in c.list_artifacts(run_id)]
    return result


def best_run(metric: str = "f1", limit: int = 5, direction: str = "max") -> dict:
    if direction not in {"max", "min"}:
        raise ValueError("direction must be max or min")
    runs = list_runs(limit)["runs"]
    eligible = [r for r in runs if r["status"] == "FINISHED"
                and math.isfinite(r["metrics"].get(metric, float("nan")))]
    chosen = (max if direction == "max" else min)(
        eligible, key=lambda r: r["metrics"][metric], default=None)
    return {"best": chosen, "comparison": runs, "metric": metric, "direction": direction,
            "selection_scope": f"latest {limit} runs in {settings.mlflow_experiment}",
            "caution": "Metric rank alone does not establish production readiness"}


def compare_runs(run_ids: list[str]) -> dict:
    if not 2 <= len(run_ids) <= 10:
        raise ValueError("Provide between two and ten run IDs")
    return {"runs": [run_details(r) for r in run_ids]}


def compare_experiments(experiment_ids: list[str], limit: int = 5) -> dict:
    if not 2 <= len(experiment_ids) <= 10 or not 1 <= limit <= 100:
        raise ValueError("Provide two to ten experiments and a limit from 1 to 100")
    c = client()
    return {"experiments": [{"experiment_id": eid,
                             "runs": [serialize(r) for r in c.search_runs(
                                 [eid], max_results=limit,
                                 order_by=["attributes.start_time DESC"])]}
                            for eid in experiment_ids]}


def registry() -> dict:
    return {"models": [{"name": m.name, "versions": [v.version for v in m.latest_versions]}
                       for m in client().search_registered_models(max_results=50)]}
