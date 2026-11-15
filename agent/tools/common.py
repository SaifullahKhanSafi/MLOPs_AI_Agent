import re
import subprocess

from agent.config import settings


def command(args: list[str]) -> str:
    """Only internal callers construct argv; no shell or arbitrary user commands."""
    result = subprocess.run(
        args, cwd=settings.repo_root, capture_output=True, text=True,
        timeout=settings.tool_timeout, check=False, shell=False,
    )
    if result.returncode:
        # Never return raw stderr: tools can print credentials, URLs or local secrets.
        raise RuntimeError(f"{args[0]} operation failed (exit {result.returncode})")
    return result.stdout


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,199}", value):
        raise ValueError("Invalid identifier")
    return value


def revision(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@/~-]{0,99}", value):
        raise ValueError("Invalid Git revision")
    return value
