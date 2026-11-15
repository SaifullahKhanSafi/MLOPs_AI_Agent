# Assignment 03 technical report

## System and tool definitions

The implementation combines a workstation conversational operator, real DVC/Git
provenance, an MLflow tracking server, a PostgreSQL-backed Airflow 3 LocalExecutor,
and a Kubernetes-hosted FastAPI Iris classifier. The full system diagram and tool
permission table are in [architecture.md](architecture.md). Each module offers at
least four typed callable tools. [README.md](README.md) contains reproducible setup,
service launch, deployment, interaction and failure-injection commands.

The classifier uses a seeded stratified 75/25 split and 100-tree random forest.
Macro F1 and accuracy are logged in MLflow along with model artifacts, parameters,
Git commit and DVC hash. A 0.90 macro-F1 gate controls local model promotion; it
does not automatically deploy. Kubernetes has two desired replicas, a ClusterIP
Service, ConfigMap, CPU/memory requests/limits, probes and non-root execution.

## Verification results

See [STATUS.md](STATUS.md) for actual workspace verification. Code and automated
tests are distinct from live service evidence. Any unavailable infrastructure must
remain marked pending until its exported responses have been reviewed.

## Five conversations and actual evidence

Run `python scripts/collect_evidence.py` after bringing up the services. It records
timestamps, the exact prompts, request identifiers, answers, and actual tool
responses. Preserve reviewed files in `evidence/submission/` and link them below.

| Scenario | Required result to verify | Final evidence |
|---|---|---|
| Dataset provenance | Actual commit and MD5 match DVC and MLflow tags | Pending live capture/review |
| Candidate selection | Last five recorded runs, F1 comparison and readiness caveat | Pending live capture/review |
| Pipeline execution | Actual DAG ID/run ID, terminal state and task statuses | Pending live capture/review |
| Deployment diagnosis | Two desired replicas, actual availability, image/run ID, events/logs | Pending live capture/review |
| Multi-tool reasoning | Correlated results from all four integrations; no automatic retraining | Pending live capture/review |

Capture screenshots of each service for the defense. JSON exports are acceptable
evidence too, but must show actual service responses rather than example values.

## Failure investigation 1: validation rejection

Injection: `python scripts/failure_demo.py validation --confirm` triggers the real
DAG with `fail_validation=true`. Expected root cause is the intentional validation
exception. After retries, `validate` should fail and later stages should be
`upstream_failed`, with no model promotion. Ask the agent for pipeline diagnostics;
verify it reads the failed task and available logs. Resolve by triggering a normal
run without the injection, then verify all tasks succeed. Actual run ID, log
excerpt, downstream states and recovered run ID: **pending live capture**.

## Failure investigation 2: quality-gate rejection

Injection: `python scripts/failure_demo.py quality --confirm` triggers the real DAG
with `force_quality_failure=true`. Expected root cause is the intentional gate
rejection after evaluation has logged an MLflow run. The run should have
`quality_gate=failed`; the last approved model should stay unchanged. Resolve by
removing the injection, run normally, and verify the gate/model metadata. A unit
test independently verifies that gate rejection preserves the promoted artifact.
Actual failed run, MLflow tag, artifact comparison and recovered run ID:
**pending live capture**.

## Defense notes

- DVC identifies data through content hashes and Git-linked metadata; Git alone
  does not store the raw DVC dataset.
- MLflow supplies measured candidates and lineage, not guaranteed production fitness.
- Airflow owns retry/dependency scheduling; a submitted run is not a completed run.
- Kubernetes readiness controls Service traffic; liveness handles process recovery.
- The LLM selects typed tools; explicit confirmation and allowlists live outside it.
- When diagnosing an unexpected outage, begin with returned errors, pod readiness,
  events and application logs; correlate rather than guessing a root cause.

## Limitations and improvements

This is a local production-oriented assignment implementation, not a hardened
multi-tenant platform. Shared training artifacts prevent concurrent DVC/DAG runs;
confirmation tokens are process-local; the optional LLM can interpret evidence
incorrectly; no live drift measurements are available; data is a small benchmark;
no automatic deployment is enabled; model registry inspection is supported but
training does not register a release automatically. Dependencies are pinned at
the direct level; transitive resolution can vary. Improvements include per-run
artifact isolation, a distributed confirmation store, OIDC/TLS, constrained
service accounts, a persistent shared DVC remote, model approval/registry aliases,
drift monitoring, durable audit storage and dedicated live-integration CI.
