from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, get_current_context, task


@dag(
    dag_id="training_pipeline", schedule=None, catchup=False, max_active_runs=1,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15)},
    tags=["mlops", "assignment03"],
)
def training_pipeline():
    @task
    def stage(name: str):
        from training.train import run_stage

        context = get_current_context()
        conf = context["dag_run"].conf or {}
        allowed = {k: bool(conf.get(k, False)) for k in (
            "fail_validation", "force_quality_failure")}
        run_stage(name, allowed)

    validation = stage.override(task_id="validate")("validate")
    preprocessing = stage.override(task_id="preprocess")("preprocess")
    training = stage.override(task_id="train")("train")
    evaluation = stage.override(task_id="evaluate_mlflow")("evaluate")
    gate = stage.override(task_id="quality_gate")("quality_gate")
    validation >> preprocessing >> training >> evaluation >> gate


training_pipeline()
