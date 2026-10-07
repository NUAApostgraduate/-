"""Launch the HTTP backend independently from the interactive batch window."""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the translator backend as a detached process.")
    parser.add_argument("--python", required=True, dest="python_executable")
    parser.add_argument("--server", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8765")
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [args.python_executable, "-B", args.server, "--host", args.host, "--port", str(args.port)]
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    with log_path.open("ab", buffering=0) as log_file:
        log_file.write(b"\n--- starting detached translator backend ---\n")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(Path(args.server).resolve().parent),
            creationflags=creationflags,
            close_fds=True,
            env=os.environ.copy(),
        )

    print(f"Started detached backend process (PID {process.pid}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
