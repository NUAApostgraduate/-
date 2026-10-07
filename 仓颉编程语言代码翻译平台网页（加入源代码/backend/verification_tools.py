"""Execute real Cangjie build commands and preserve compiler output."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def verify_cangjie_artifact(output_dir: str, compiler_command: str = "cjc", build_command: str = "cjpm build") -> dict:
    root = Path(output_dir)
    cjpm = build_command.split()[0]
    cjc = compiler_command.split()[0]
    if not root.exists():
        return {"attempted": False, "build_verified": False, "status": "artifact_missing", "log": "Generated artifact directory does not exist."}
    if (root / "cjpm.toml").exists():
        if not shutil.which(cjpm):
            return {"attempted": False, "build_verified": False, "status": "compiler_unavailable", "command": build_command, "log": "cjpm is required to verify the complete generated project."}
        if not (root / "src").exists() or not any((root / "src").glob("*.cj")):
            return {"attempted": True, "build_verified": False, "status": "source_missing", "command": build_command, "log": "No .cj source file exists directly in src/; cjpm would skip nested source directories."}
        command = build_command.split()
    else:
        source_files = list((root / "src").glob("*.cj")) if (root / "src").exists() else list(root.glob("*.cj"))
        if not shutil.which(cjc):
            return {"attempted": True, "build_verified": False, "status": "compiler_unavailable", "command": build_command if (root / "cjpm.toml").exists() else cjc, "log": "Install Cangjie SDK and ensure cjc/cjpm is on PATH."}
        if not source_files:
            return {"attempted": True, "build_verified": False, "status": "source_missing", "command": cjc, "log": "No .cj source file was generated."}
        command = [cjc, str(source_files[0])]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        log = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
        return {"attempted": True, "build_verified": completed.returncode == 0, "status": "passed" if completed.returncode == 0 else "failed", "command": command, "returncode": completed.returncode, "log": log[-12000:]}
    except subprocess.TimeoutExpired:
        return {"attempted": True, "build_verified": False, "status": "timeout", "command": command, "log": "Build exceeded 120 seconds."}
    except Exception as exc:
        return {"attempted": True, "build_verified": False, "status": "execution_error", "command": command, "log": str(exc)}
