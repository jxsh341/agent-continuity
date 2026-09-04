from pathlib import Path
import subprocess


def evaluate_workspace(workspace: Path) -> dict:
    """Deterministic evaluator boundary; never an LLM judge."""
    if not workspace.exists():
        return {"task_success": False, "workspace_exists": False}
    return {"task_success": True, "workspace_exists": True}


def run_command(workspace: Path, *args: str) -> dict:
    p = subprocess.run(args, cwd=workspace, capture_output=True, text=True)
    return {
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "passed": p.returncode == 0,
    }
