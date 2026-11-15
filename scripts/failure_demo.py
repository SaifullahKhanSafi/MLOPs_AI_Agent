"""Inject an Airflow failure, wait, and export actual diagnostic evidence."""
import argparse
import json
import time
from pathlib import Path

from agent.config import settings
from agent.registry import redact
from agent.tools import airflow_tools as af


def main():
    p = argparse.ArgumentParser()
    p.add_argument("scenario", choices=["validation", "quality"])
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--run-id", help="Read an existing injected run instead of triggering one")
    args = p.parse_args()
    flag = "fail_validation" if args.scenario == "validation" else "force_quality_failure"
    if args.run_id:
        run = af.dag_run(settings.approved_dag, args.run_id)
        if run.get("conf", {}).get(flag) is not True:
            raise SystemExit("Existing run does not match the requested injection scenario")
    else:
        if not args.confirm:
            raise SystemExit(f"Will trigger training_pipeline with {flag}=true; rerun with --confirm")
        run = af.trigger_dag(settings.approved_dag, {flag: True})
    run_id = run["dag_run_id"]
    for _ in range(120):
        final_run = af.dag_run(settings.approved_dag, run_id)
        if final_run["state"] == "failed":
            break
        if final_run["state"] == "success":
            raise SystemExit("Injected run succeeded unexpectedly; do not claim a reproduced failure")
        time.sleep(5)
    else:
        raise SystemExit("Timed out; query Airflow manually. Do not claim failure was reproduced.")
    tasks = af.task_instances(settings.approved_dag, run_id)
    logs = {}
    for task in tasks.get("task_instances", []):
        if task.get("state") == "failed":
            logs[task["task_id"]] = af.task_logs(settings.approved_dag, run_id,
                                               task["task_id"], task.get("try_number", 1))
    out = Path("evidence/live")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"failure-{args.scenario}.json").write_text(json.dumps(redact({
        "run": run, "final_run": final_run, "tasks": tasks, "logs": logs}),
        indent=2), encoding="utf-8")
    print(f"Captured actual {args.scenario} failure. Trigger a normal run afterward to recover.")


if __name__ == "__main__":
    main()
