"""Generate local secrets and a dataset. Does not commit, push, or deploy anything."""
import json
import secrets
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    env_path = ROOT / ".env"
    values = dict(dotenv_values(ROOT / ".env.example"))
    if env_path.exists():
        values.update(dotenv_values(env_path))
    for name in ("AGENT_API_KEY", "AIRFLOW_PASSWORD", "POSTGRES_PASSWORD", "AIRFLOW_JWT_SECRET"):
        if not values.get(name):
            values[name] = secrets.token_hex(24)
    env_path.write_text("\n".join(f"{k}={v or ''}" for k, v in values.items()) + "\n")
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "airflow-passwords.json").write_text(json.dumps({"admin": values["AIRFLOW_PASSWORD"]}))
    subprocess.run([__import__("sys").executable, "-m", "training.generate_data"],
                   cwd=ROOT, check=True)
    print("Local .env, Airflow password file and dataset prepared. Secrets were not printed.")


if __name__ == "__main__":
    main()
