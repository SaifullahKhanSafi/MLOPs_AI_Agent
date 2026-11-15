# Production MLOps AI Agent

An evidence-driven conversational operator for DVC, MLflow, Apache Airflow 3 and
Kubernetes. Includes a reproducible Iris classifier, a five-stage training DAG,
quality-gated model promotion, FastAPI inference, two Kubernetes replicas and CI.

The agent runs on your workstation so it can inspect your Git/DVC repository and
use your kubeconfig. Kubernetes runs the inference service. There are no fabricated
service responses in normal operation. An unavailable tool returns an explicit error.

## 1. Requirements

- Python 3.12 and Git.
- Docker Desktop using Linux containers and Compose v2. Allow room for multiple
  ML images: at least 10 GB free disk is recommended. Avoid parallel image builds
  on an 8 GB RAM workstation; allow 4-6 GB to Docker when resources permit.
- Docker Desktop **Settings > Kubernetes > Enable Kubernetes**, then wait for Ready.
- `kubectl` on PATH; `kubectl config current-context` should show `docker-desktop`.
- An OpenAI API key for LLM mode. Rules mode works without a paid key but is a
  deterministic integration/diagnostic mode, not an LLM demonstration.

Use PowerShell from this project directory. Commands below assume the repository
has already been cloned. To start on another computer:

```powershell
git clone https://github.com/SaifullahKhanSafi/MLOPs_AI_Agent.git
cd MLOPs_AI_Agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:Path = "$PWD\.venv\Scripts;$env:Path"
python scripts/bootstrap.py
```

After cloning, an automated alternative for environment installation, service launch,
training, lint and tests is `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`.
Add `-Deploy` to explicitly request deployment after enabling Kubernetes. The
step-by-step instructions below explain each operation and troubleshooting.

For an existing environment, just set PATH and rerun bootstrap if needed. Bootstrap
preserves existing `.env` values, generates local secrets without printing them,
writes Airflow's password file, and regenerates the public Iris dataset.
Never commit `.env`, `runtime/`, kubeconfig, or API keys.

## 2. Dataset versioning

The committed `data/iris.csv.dvc` records the dataset hash. On the prepared repository:

```powershell
dvc status
```

For a fresh dataset change, record the data **before training**:

```powershell
dvc add data/iris.csv
git add data/iris.csv.dvc
git commit -m "Version Iris dataset"
```

If bootstrapping a copy without DVC metadata, first run `dvc init`.
Create a local demonstration remote (use an absolute path):

```powershell
New-Item -ItemType Directory -Force runtime/dvc-remote
$dataRemote = (Resolve-Path runtime/dvc-remote).Path
dvc remote add --local -d local-store $dataRemote
dvc push data/iris.csv.dvc
```

This remote is machine-local. For submission on another machine either regenerate
the included public dataset with bootstrap and verify `dvc status`, or configure
your own persistent DVC remote and `dvc pull`. GitHub stores metadata, not DVC data.
No cloud account or shared credentials are required for this assignment.

To reproduce a historical version safely:

```powershell
# Replace COMMIT with git_commit from the selected MLflow run.
git worktree add ../mlops-reproduce COMMIT
cd ../mlops-reproduce
# Configure the same absolute DVC remote in this worktree if needed.
dvc remote add --local -d local-store ABSOLUTE_REMOTE_PATH
dvc pull data/iris.csv.dvc
# Use the original project's Python environment, or install one here.
dvc repro
```

`dvc diff OLD_COMMIT NEW_COMMIT` compares versions without changing the active tree.
The agent's `dvc_version` returns the recorded hash, commit and reproduction steps.

## 3. Start MLflow and Airflow 3

```powershell
docker compose --parallel 1 up -d --build
docker compose ps
docker compose logs --tail=40 airflow
```

The first build downloads large images. Wait until healthy. MLflow is
http://localhost:5000; Airflow is http://localhost:8080. Airflow username is `admin`;
use `AIRFLOW_PASSWORD` from your local `.env`. Compose uses PostgreSQL and Airflow's
LocalExecutor; `airflow standalone` starts its API, scheduler, DAG processor and
triggerer. Services bind to localhost for this development environment.

The agent authenticates at `/auth/token` and uses `/api/v2`, not Airflow 2's API.
New DAGs are created unpaused. If an existing `training_pipeline` is paused, unpause
it in the UI before triggering it. If it is missing,
run `docker compose exec airflow airflow dags list-import-errors`.

## 4. Train and verify provenance

For the first locally trained model:

```powershell
dvc repro
git add dvc.lock
git commit -m "Record reproducible training pipeline"
```

The pipeline validates data, creates a stratified split, trains a seeded random
forest, logs F1/accuracy/model/provenance to MLflow, and applies `MIN_F1=0.90`.
Only a passed gate writes `artifacts/model.joblib` and `model_metadata.json`.
MLflow run tags include `git_commit`, `dataset_md5`, `dvc_file`, `quality_gate`.
These refer to the dataset commit; later commits of generated `dvc.lock` do not
change which data was used. `dvc repro --force` creates a fresh tracked experiment.
Do not run DVC training and the Airflow DAG concurrently; they share `artifacts/`.

For an actual Airflow run:

```powershell
python -m agent.main
```

Enter `trigger training`, review the proposed DAG, then enter `confirm`.
Ask `Report training pipeline status and failed tasks` repeatedly until its terminal
state. A trigger acknowledgment proves submission only; it does not prove success.
Airflow runs have retries, explicit dependencies and one active run at a time.

If Docker is unavailable, local pipeline verification can use SQLite tracking:

```powershell
$env:MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
dvc repro --force
# Return to the shared server afterward:
Remove-Item Env:MLFLOW_TRACKING_URI
```

Local SQLite runs and Compose MLflow runs are separate stores. Train against the
Compose server before collecting final multi-tool evidence.

## 5. Deploy the approved model

Enable Docker Desktop Kubernetes, then:

```powershell
kubectl get nodes
# Preview the exact image/run ID and namespace:
python scripts/deploy.py
# Explicitly approve the displayed local deployment:
python scripts/deploy.py --confirm
kubectl -n mlops-agent get pods,deployments,services
kubectl -n mlops-agent port-forward service/iris-api 8001:80
```

Leave port forwarding running in a separate terminal. The deployment uses an image
tag equal to the actual MLflow run ID and labels pods with `model-run-id`; readiness
returns the baked model metadata. Retraining does not silently redeploy: run the
deployment script again for an approved replacement. Docker Desktop shares its
local image store with its Kubernetes cluster. For kind/minikube, load the image
into that cluster first. For a remote cluster, push it to an accessible registry and
adapt the manifest image.

Test from another PowerShell terminal:

```powershell
Invoke-RestMethod http://localhost:8001/health/ready
$body = @{ instances = @(@(5.1,3.5,1.4,0.2)) } | ConvertTo-Json -Depth 5
Invoke-RestMethod http://localhost:8001/predict -Method Post -ContentType application/json -Body $body
```

The inference container contains only prediction dependencies and has no Kubernetes
credentials or `/chat` route. Use the workstation agent for operations.

## 6. Use the intelligent agent

Edit `.env` locally:

```dotenv
AGENT_MODE=llm
OPENAI_API_KEY=your-own-key
OPENAI_MODEL=gpt-4o-mini
```

The model is configurable for your account. Restart the CLI/API after editing.
LLM mode uses structured Chat Completions function calls, bounded tool rounds and
actual tool results. API usage can incur charges. For free local integration checks,
use `AGENT_MODE=rules`. All ordinary tests mock external systems and the model.

```powershell
python -m agent.main
# Or serve the conversational REST API on localhost:
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

FastAPI docs: http://localhost:8000/docs. `/chat` requires `X-API-Key` equal to your
generated `AGENT_API_KEY` in `.env`. Send `{"message":"..."}`. When a mutation is
proposed, inspect `proposed_action`, then send
`{"message":"confirm","confirmation_token":"TOKEN_FROM_RESPONSE"}` to the same
server process with the same API key. Tokens expire after five minutes and are
single use. Run one API worker: confirmation state is currently in memory.

Five evaluation conversations:

1. `Which dataset version is currently tracked?`
2. `Compare the last five training runs and recommend the best model based on F1.`
3. `Report the training pipeline status and failed tasks.`
4. `Why is my prediction API unavailable? Check deployment health.`
5. `Find the best recent model, identify the dataset version used to train it, check deployment status, and explain whether retraining is necessary.`

The last request never authorizes retraining. Recommendations require a recorded
failed gate or the explicit configurable `MAX_MODEL_AGE_DAYS=30` freshness policy.
The example has no drift monitor and does not infer degradation from low pod health.

## 7. Tests, failure investigations and evidence

```powershell
ruff check .
pytest -q
python scripts/collect_evidence.py
```

Ordinary CI runs lint and mocked tests. A separate CI job performs real DVC training
with SQLite MLflow, builds the inference image and calls its health/prediction APIs.
It does not call a live Kubernetes cluster, Airflow installation or paid model.

Two real, controlled failures (ensure DAG is unpaused):

```powershell
python scripts/failure_demo.py validation --confirm
python -m agent.main "Report training pipeline status and failed tasks"
python scripts/failure_demo.py quality --confirm
python -m agent.main "Report training pipeline status and failed tasks"
```

Validation failure stops all later stages; quality failure tags the run as failed
and preserves the last approved model. Both retry before failing. Remove the
injection by triggering a normal run and confirm recovery. The scripts export real
task states/logs and time out rather than manufacture a successful demonstration.

`evidence/live/` is ignored because logs may contain environment-specific data.
Review/redact exported JSON before intentionally adding selected files to
`evidence/submission/`. Capture screenshots of DVC status/hash, MLflow run metrics
and tags, the successful Airflow task graph, and Kubernetes replicas/health into
`screenshots/`. Complete the actual-results sections in [REPORT.md](REPORT.md).
Do not present mocked tests as live infrastructure evidence.

## 8. Troubleshooting and manual steps

| Symptom | Action |
|---|---|
| Docker engine pipe missing | Start Docker Desktop and wait for Linux engine Ready. |
| Docker engine exits during builds | Check Docker resource limits and free disk; build services sequentially, then retry. |
| `kubernetes.docker.internal` unresolved | Enable Kubernetes in Docker Desktop; wait for startup, then verify `kubectl get nodes`. |
| Airflow cannot authenticate | Rerun bootstrap, verify `.env` password matches `runtime/airflow-passwords.json`, restart Airflow. |
| DAG queued indefinitely | Unpause DAG, inspect scheduler health and import errors. |
| `dvc` not found | Add `.venv/Scripts` to PATH in the current terminal. |
| Dataset provenance mismatch | Run `dvc add data/iris.csv`, commit its `.dvc` pointer, rerun training. |
| Inference readiness 503 | Train successfully, rebuild the image, deploy that run, inspect pod logs. |
| ImagePullBackOff | Load the image into your local cluster or use a reachable registry. |
| MLflow empty after switching URI | Train against that tracking server; local SQLite is separate. |
| 403 on restart | Use only `mlops-agent` and explicitly confirm; your kubeconfig must allow patching its deployment. |

Manual items: enable Kubernetes, provide your own LLM key, review action confirmations,
review/commit live evidence, and ensure GitHub Actions is enabled. No GitHub Actions
secrets are needed for the included CI. The code supports real integrations, but a
successful unit test run does not establish that your cluster or DAG is healthy.

See [architecture.md](architecture.md) for permissions, design and upstream sources,
[REPORT.md](REPORT.md) for the engineering report, and [STATUS.md](STATUS.md) for
what was actually verified in this workspace.
