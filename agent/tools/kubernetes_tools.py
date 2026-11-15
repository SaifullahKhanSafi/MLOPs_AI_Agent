import json

from agent.config import settings
from agent.tools.common import command, identifier


def kubectl(args: list[str], namespace: str | None = None) -> str:
    ns = namespace or settings.approved_namespace
    if ns != settings.approved_namespace:
        raise PermissionError("Namespace is outside the approved allowlist")
    return command(["kubectl", "--request-timeout=15s", "-n", ns, *args])


def workloads() -> dict:
    return json.loads(kubectl(["get", "pods,deployments", "-l", "app=iris-api", "-o", "json"]))


def services() -> dict:
    return json.loads(kubectl(["get", "services", "-l", "app=iris-api", "-o", "json"]))


def events() -> dict:
    return json.loads(kubectl(["get", "events", "--sort-by=.lastTimestamp", "-o", "json"]))


def pod_logs(pod: str, previous: bool = False) -> dict:
    pod = identifier(pod)
    obj = json.loads(kubectl(["get", "pod", pod, "-o", "json"]))
    if obj.get("metadata", {}).get("labels", {}).get("app") != "iris-api":
        raise PermissionError("Only application pod logs are allowed")
    args = ["logs", pod, "--tail=100"]
    if previous:
        args.append("--previous")
    return {"pod": pod, "logs": kubectl(args)}


def restart_deployment(namespace: str, confirmed: bool = False) -> dict:
    # Defense in depth. The registry supplies this flag only after token verification.
    if not confirmed:
        raise PermissionError("Explicit confirmation is required")
    return {"output": kubectl(["rollout", "restart", "deployment/iris-api"], namespace)}
