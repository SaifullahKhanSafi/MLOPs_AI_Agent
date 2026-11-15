import argparse
import hashlib
import json
import logging
import os

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from agent.config import settings
from agent.tools.common import command

FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
ROOT = settings.repo_root
OUT = ROOT / "artifacts"
log = logging.getLogger(__name__)


def write_json(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def validate(fail_validation=False, **_):
    frame = pd.read_csv(ROOT / "data/iris.csv")
    if fail_validation:
        raise ValueError("Injected validation failure: missing target column")
    if list(frame.columns) != FEATURES + ["target"] or len(frame) < 30:
        raise ValueError("Invalid dataset schema or insufficient rows")
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Dataset contains missing or non-finite values")
    if not frame.target.isin([0, 1, 2]).all() or frame.target.value_counts().min() < 5:
        raise ValueError("Invalid or insufficient target classes")
    if (frame[FEATURES] <= 0).any().any():
        raise ValueError("Feature lengths must be positive")
    write_json("validation.json", {"rows": len(frame), "valid": True})


def preprocess(**_):
    frame = pd.read_csv(ROOT / "data/iris.csv")
    x_train, x_test, y_train, y_test = train_test_split(
        frame[FEATURES].to_numpy(), frame.target.to_numpy(),
        test_size=0.25, random_state=42, stratify=frame.target)
    OUT.mkdir(exist_ok=True)
    np.savez(OUT / "processed.npz", x_train=x_train, x_test=x_test,
             y_train=y_train, y_test=y_test)


def train(**_):
    data = np.load(OUT / "processed.npz")
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=1)
    model.fit(data["x_train"], data["y_train"])
    joblib.dump(model, OUT / "candidate.joblib")


def provenance():
    raw = (ROOT / "data/iris.csv").read_bytes()
    digest = hashlib.md5(raw).hexdigest()  # DVC's content-address hash, not a security hash.
    pointer = yaml.safe_load((ROOT / "data/iris.csv.dvc").read_text())
    commit = command(["git", "rev-parse", "HEAD"]).strip()
    committed = yaml.safe_load(command(["git", "show", f"{commit}:data/iris.csv.dvc"]))
    if pointer["outs"][0]["md5"] != digest or committed != pointer:
        raise ValueError("Dataset is not the DVC version recorded in Git; dvc add and commit first")
    return {"git_commit": commit, "dataset_md5": digest, "dvc_file": "data/iris.csv.dvc"}


def evaluate(**_):
    data = np.load(OUT / "processed.npz")
    model = joblib.load(OUT / "candidate.joblib")
    predictions = model.predict(data["x_test"])
    metrics = {"f1": f1_score(data["y_test"], predictions, average="macro"),
               "accuracy": accuracy_score(data["y_test"], predictions)}
    tags = provenance()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment)
    with mlflow.start_run() as run:
        mlflow.log_params({"n_estimators": 100, "max_depth": 5, "random_state": 42,
                           "test_size": 0.25})
        mlflow.log_metrics(metrics)
        mlflow.set_tags({**tags, "quality_gate": "pending"})
        mlflow.log_artifact(str(ROOT / "data/iris.csv.dvc"), "provenance")
        mlflow.sklearn.log_model(
            model, name="candidate", input_example=data["x_test"][:2],
            pip_requirements=["mlflow==3.1.4", "scikit-learn==1.7.2", "numpy==2.2.6",
                              "joblib==1.5.2", "dill==0.3.1.1"],
        )
        write_json("metrics.json", metrics)
        mlflow.log_artifact(str(OUT / "metrics.json"))
        write_json("run.json", {"run_id": run.info.run_id, **tags, **metrics})
    return metrics


def quality_gate(force_quality_failure=False, **_):
    run = json.loads((OUT / "run.json").read_text())
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    client = mlflow.tracking.MlflowClient()
    passed = run["f1"] >= settings.min_f1 and not force_quality_failure
    client.set_tag(run["run_id"], "quality_gate", "passed" if passed else "failed")
    if not passed:
        raise ValueError(f"Quality gate failed: F1={run['f1']:.4f}, minimum={settings.min_f1}")
    # The previously promoted model survives a failed gate.
    staging = OUT / "model.joblib.tmp"
    staging.write_bytes((OUT / "candidate.joblib").read_bytes())
    os.replace(staging, OUT / "model.joblib")
    write_json("model_metadata.json", {**run, "quality_gate": "passed"})


STAGES = {"validate": validate, "preprocess": preprocess, "train": train,
          "evaluate": evaluate, "quality_gate": quality_gate}


def run_stage(stage, conf=None):
    log.info("Starting training stage %s", stage)
    STAGES[stage](**(conf or {}))
    log.info("Completed training stage %s", stage)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=[*STAGES, "all"], default="all", nargs="?")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    for stage in STAGES if args.stage == "all" else [args.stage]:
        run_stage(stage)


if __name__ == "__main__":
    main()
