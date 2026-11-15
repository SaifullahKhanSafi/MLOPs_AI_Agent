import inspect
import json
import logging
import re
import subprocess
import time
from typing import get_type_hints

import httpx
from pydantic import ConfigDict, create_model

from agent.config import settings
from agent.schemas import ToolResult
from agent.tools import airflow_tools as af
from agent.tools import dvc_tools as dv
from agent.tools import kubernetes_tools as ku
from agent.tools import mlflow_tools as mf

log = logging.getLogger("mlops.tools")


def redact(value):
    text = json.dumps(value, default=str)
    for secret in (settings.openai_api_key, settings.airflow_password, settings.agent_api_key):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(bearer\s+)[a-z0-9._-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:password|token|api_key|secret)[\"'\s:=]+)[^\s,\"'}]+",
                  r"\1[REDACTED]", text)
    return json.loads(text)


class Registry:
    def __init__(self):
        self.functions = {
            "dvc_list": dv.list_datasets, "dvc_version": dv.dataset_version,
            "dvc_status": dv.data_status, "dvc_compare": dv.compare_versions,
            "mlflow_experiments": mf.list_experiments, "mlflow_runs": mf.list_runs,
            "mlflow_run": mf.run_details, "mlflow_best": mf.best_run,
            "mlflow_compare": mf.compare_runs, "mlflow_registry": mf.registry,
            "mlflow_compare_experiments": mf.compare_experiments,
            "airflow_dags": af.list_dags, "airflow_runs": af.dag_runs,
            "airflow_tasks": af.task_instances, "airflow_logs": af.task_logs,
            "airflow_trigger": af.trigger_dag,
            "k8s_workloads": ku.workloads, "k8s_services": ku.services,
            "k8s_events": ku.events, "k8s_logs": ku.pod_logs,
            "k8s_restart": ku.restart_deployment,
        }
        self.mutations = {"airflow_trigger", "k8s_restart"}
        self.models = {}
        for name, fn in self.functions.items():
            types = get_type_hints(fn)
            fields = {p.name: (types[p.name], ... if p.default is p.empty else p.default)
                      for p in inspect.signature(fn).parameters.values()
                      if p.name != "confirmed"}
            self.models[name] = create_model(name, __config__=ConfigDict(extra="forbid"), **fields)

    def definitions(self):
        return [{"type": "function", "function": {"name": name,
                 "description": (fn.__doc__ or name.replace("_", " "))[:500],
                 "parameters": self.models[name].model_json_schema()}}
                for name, fn in self.functions.items()]

    def execute(self, name: str, args: dict, request_id: str, authorized: bool = False):
        start = time.monotonic()
        status, data, error = "ok", None, None
        try:
            if name not in self.functions:
                raise ValueError("Unknown tool")
            args = self.models[name].model_validate(args).model_dump()
            if name in self.mutations and not authorized:
                raise PermissionError("Explicit confirmation required for this action")
            if name == "k8s_restart":
                args["confirmed"] = authorized
            data = redact(self.functions[name](**args))
        except PermissionError:
            status, error = "denied", "Action denied by permission policy"
        except (TimeoutError, httpx.TimeoutException, subprocess.TimeoutExpired):
            status, error = "error", "Tool timed out; operational state is unknown"
        except Exception as exc:
            # Exception type is useful; exception messages may contain tokens/credentials.
            status, error = "error", f"{type(exc).__name__}: tool failed; state is unknown"
        duration = round((time.monotonic() - start) * 1000, 2)
        log.info(json.dumps({"tool": name, "status": status,
                             "duration_ms": duration, "request_id": request_id}))
        return ToolResult(tool=name, status=status, data=data, error=error,
                          duration_ms=duration, request_id=request_id)
