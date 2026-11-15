"""Build an immutable image and deploy the exact quality-gated model to local Kubernetes."""
import argparse
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--confirm", action="store_true", help="Explicitly approve namespace changes")
    args = p.parse_args()
    metadata = json.loads((ROOT / "artifacts/model_metadata.json").read_text())
    if metadata.get("quality_gate") != "passed":
        raise SystemExit("Only a quality-gated model can be deployed")
    image = f"mlops-iris:{metadata['run_id']}"
    print(f"Deployment: mlops-agent/iris-api, replicas=2, image={image}")
    if not args.confirm:
        raise SystemExit("Review the action above and rerun with --confirm to deploy")
    run(["docker", "build", "-t", image, "."])
    run(["kubectl", "apply", "-f", "kubernetes/namespace.yaml"])
    for file in ("configmap.yaml", "service.yaml", "rbac.yaml"):
        run(["kubectl", "apply", "-f", f"kubernetes/{file}"])
    deployment = yaml.safe_load((ROOT / "kubernetes/deployment.yaml").read_text())
    template = deployment["spec"]["template"]
    template["spec"]["containers"][0]["image"] = image
    template["metadata"]["labels"]["model-run-id"] = metadata["run_id"]
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    manifest = runtime / "deployment.yaml"
    manifest.write_text(yaml.safe_dump(deployment))
    run(["kubectl", "apply", "-f", str(manifest)])
    run(["kubectl", "-n", "mlops-agent", "rollout", "status", "deployment/iris-api", "--timeout=180s"])


if __name__ == "__main__":
    main()
