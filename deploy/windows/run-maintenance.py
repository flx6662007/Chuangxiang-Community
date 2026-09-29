"""Run scheduled maintenance without allocating a Windows console window."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("ingest", "settle"), required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    backend = repo_root / "backend"
    python = backend / ".venv" / "Scripts" / "python.exe"
    log_dir = repo_root / ".local" / "maintenance"
    log_dir.mkdir(parents=True, exist_ok=True)
    commands = (
        [
            ["sync_competitions", "--trigger", "scheduled", "--auto-accept", "--enable-recruitment"],
            ["sync_competition_catalog", "--limit", "300", "--max-pages", "3"],
            ["process_catalog_notices", "--scheduled"],
            ["fetch_catalog_attachments", "--limit", "40"],
            ["process_catalog_notices", "--scheduled"],
        ]
        if args.task == "ingest"
        else [["settle_team_deadlines"]]
    )
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    result_code = 0
    with (log_dir / f"{args.task}-latest.log").open("w", encoding="utf-8") as log:
        print(f"Started: {datetime.now().astimezone().isoformat()}", file=log, flush=True)
        for command in commands:
            try:
                # pythonw has no console. Prevent child python.exe from creating one too.
                result = subprocess.run(
                    [str(python), "manage.py", *command],
                    cwd=backend,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    check=False,
                )
                if result.returncode:
                    result_code = result.returncode
            except OSError as error:
                print(f"Launch failed ({command[0]}): {error}", file=log, flush=True)
                result_code = 1
        print(
            f"Finished: {datetime.now().astimezone().isoformat()}; exit={result_code}",
            file=log,
            flush=True,
        )
    return result_code


if __name__ == "__main__":
    sys.exit(main())
