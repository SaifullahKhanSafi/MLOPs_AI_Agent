"""Trigger the approved real DAG, wait for a terminal state, and export evidence."""
import argparse
import json
import time
from pathlib import Path

from agent.config import settings
from agent.registry import redact
from agent.tools import airflow_tools as af


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    print(f"Action: trigger approved DAG {settings.approved_dag} at {settings.airflow_url}")
    if not args.confirm:
        raise SystemExit("Review this action and rerun with --confirm")
    if not 1 <= args.timeout <= 3600:
        raise SystemExit("Timeout must be between 1 and 3600 seconds")
    submitted = af.trigger_dag(settings.approved_dag)
    run_id = submitted["dag_run_id"]
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        run = af.dag_run(settings.approved_dag, run_id)
        if run["state"] in {"success", "failed"}:
            break
        time.sleep(5)
    else:
        raise SystemExit(f"Run {run_id} has not reached a verified terminal state; inspect Airflow")
    tasks = af.task_instances(settings.approved_dag, run_id)
    evidence = redact({"submitted": submitted, "final_run": run, "tasks": tasks})
    target = Path("evidence/live/airflow-run.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Verified run {run_id}: {run['state']}; evidence saved to {target}")
    if run["state"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
