import json
import sys
from pathlib import Path

import yaml

from agent.config import settings
from agent.tools.common import command, revision


def list_datasets() -> dict:
    paths = sorted(settings.repo_root.glob("data/*.dvc"))
    stages = settings.repo_root / "dvc.yaml"
    return {"tracked_files": [str(p.relative_to(settings.repo_root)) for p in paths],
            "pipeline": yaml.safe_load(stages.read_text()) if stages.exists() else {}}


def dataset_version(rev: str = "HEAD") -> dict:
    rev = revision(rev)
    commit = command(["git", "rev-parse", "--verify", rev + "^{commit}"]).strip()
    metadata = command(["git", "show", f"{commit}:data/iris.csv.dvc"])
    return {"git_commit": commit, "dvc_file": "data/iris.csv.dvc",
            "outputs": yaml.safe_load(metadata)["outs"],
            "reproduce": [f"git worktree add ../mlops-reproduce {commit}",
                          "cd ../mlops-reproduce", "dvc pull", "dvc repro"]}


def data_status() -> dict:
    """Check source data; Airflow's generated training artifacts have separate freshness."""
    return {"dataset": "data/iris.csv", "changes": json.loads(command([
        sys.executable, "-m", "dvc", "status", "data/iris.csv.dvc", "--json"]))}


def compare_versions(old_rev: str, new_rev: str = "HEAD") -> dict:
    return json.loads(command([sys.executable, "-m", "dvc", "diff", "--json",
                               revision(old_rev), revision(new_rev)]))


def checkout_dataset(rev: str, output_dir: str) -> dict:
    """Reproduction helper used by CLI, never mutates the active dataset or Git tree."""
    commit = dataset_version(rev)["git_commit"]
    target = Path(output_dir).resolve()
    if target.exists():
        raise ValueError("Reproduction directory must not already exist")
    return {"commit": commit, "instructions": [f"git worktree add {target} {commit}",
                                              "Run dvc pull inside the new worktree"]}
