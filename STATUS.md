# Workspace verification status

Verified on 15 November 2026 in this workspace:

| Check | Actual result |
|---|---|
| Lint and pytest | Passed; 19 meaningful tests, with one third-party deprecation warning |
| DVC dataset | Tracked hash `4224576f0267bf88902f87f0f6200967`; local remote push and isolated-worktree pull matched |
| DVC pipeline | All five stages passed using local SQLite and the actual Docker MLflow server |
| MLflow | Real parameters, metrics, model artifacts, commit/hash tags and quality-gate tags recorded |
| Model metrics | Macro F1 `0.9229629629629629`, accuracy `0.9210526315789473`, minimum F1 `0.90` |
| Airflow 3 | Authenticated API v2 verified; real DAG parsed, all five tasks succeeded |
| Validation failure | Failed on attempt 3; all four later tasks became `upstream_failed` |
| Quality failure | First four tasks succeeded, gate failed on attempt 3; approved model run ID was preserved |
| Recovery | Normal Airflow run succeeded after both injections |
| Docker inference | Final Airflow-trained model loaded in the image; actual readiness/prediction returned HTTP 200, class 0, and matching model run ID |
| Five conversations | Exported with real tool results in rules mode; only disabled Kubernetes tools failed |
| Kubernetes | Disabled in Docker Desktop; manifests supplied, cluster deployment unverified |
| LLM provider | Structured tool-calling implementation supplied; no API key configured, provider call unverified |

Reviewed exports are in [evidence/submission](evidence/submission/). The short report
is [REPORT.md](REPORT.md); installation and service commands are in
[README.md](README.md). Follow [MANUAL_STEPS.md](MANUAL_STEPS.md) to complete the
Kubernetes and LLM demonstrations before final academic submission.

Docker's engine restarted during an earlier parallel build. Its exact cause was
not established. At the resource check this workstation had 8 GB total RAM and
about 3.4 GB free disk. The stack recovered with fewer workers and sequential
builds; inference now has its own smaller dependency set. Free disk space before
enabling Kubernetes. Airflow's model serialization dependency is explicitly pinned
in the workstation, logged model requirements and inference image.

Code, mocked CI tests, real local/Docker results and unavailable cluster/provider
checks are separate forms of evidence. No successful Kubernetes or LLM-provider
result is claimed here.
