# Remaining manual steps

The Python environment, dataset version, local DVC remote, MLflow, PostgreSQL,
Airflow DAG, trained model and tests have already been prepared in this workspace.
Read [STATUS.md](STATUS.md) for verified results. Do not submit until completing
the Kubernetes and LLM demonstration steps below.

1. **Make room for Kubernetes.** This workstation had about 3.4 GB free disk and
   8 GB total RAM during verification. Free disk space before downloading another
   cluster image set, close unnecessary apps, and review Docker Desktop resource
   limits. An engine restart interrupted an earlier build; its exact cause was
   not established. Images and services now use fewer dependencies/workers.

2. **Enable Kubernetes.** Open Docker Desktop > Settings > Kubernetes > Enable
   Kubernetes. Wait for Ready. From this project in PowerShell:

   ```powershell
   $env:Path = "$PWD\.venv\Scripts;$env:Path"
   kubectl config use-context docker-desktop
   kubectl get nodes
   python scripts/deploy.py
   # After reviewing the displayed deployment:
   python scripts/deploy.py --confirm
   kubectl -n mlops-agent get pods,deployments,services
   kubectl -n mlops-agent port-forward service/iris-api 8001:80
   ```

   In another terminal, call `http://localhost:8001/health/ready` and test `/predict`
   as shown in [README.md](README.md). Verify two replicas and the actual model run ID.

3. **Configure the LLM locally.** Edit the ignored `.env` file:

   ```dotenv
   AGENT_MODE=llm
   OPENAI_API_KEY=your-own-key
   OPENAI_MODEL=gpt-4o-mini
   ```

   Keep your key local. The current evidence uses rules mode; a real LLM-provider
   call has not been verified because no API key is configured. Model choice is
   configurable. API calls may incur usage charges.

4. **Collect final conversations and cluster evidence.** Restart the agent after
   changing `.env` and run:

   ```powershell
   python -m agent.main
   # Run in a separate terminal after interacting:
   python scripts/collect_evidence.py
   ```

   Use the five prompts in the README. Review/redact `evidence/live/`, copy approved
   conversations into `evidence/submission/`, and update the remaining pending
   entries in `REPORT.md` and `STATUS.md`. Capture screenshots in `screenshots/`.
   The existing conversations accurately report Kubernetes as unavailable; replace
   them with real healthy-cluster observations after deployment.

5. **Submit the repository and defend the design.** Check the GitHub Actions run.
   Commit your reviewed final evidence and report updates. Never add `.env`,
   kubeconfig, `runtime/`, or credentials. Use the architecture and defense notes
   in [REPORT.md](REPORT.md) to explain provenance, tool permissions, quality
   gating, retries, probes, both actual failures and successful recovery.

To rebuild the whole local environment later:
`powershell -ExecutionPolicy Bypass -File scripts/start.ps1`.
Add `-Deploy` only after Kubernetes is enabled and you intend to deploy.
