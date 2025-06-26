#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def log(msg):
    print(f"[gen_service.py] {msg}")


def fail(msg):
    log(f"❌ {msg}")
    sys.exit(1)


def conda_env_exists(env):
    try:
        result = subprocess.run(
            ["conda", "env", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
        )
        lines = result.stdout.splitlines()
        # Kolumn 0 är namnet på miljön
        return any(
            line.split()[0] == env
            for line in lines
            if line and not line.startswith("#")
        )
    except Exception as e:
        log(f"⚠️ Kunde inte kontrollera conda-miljö: {e}")
        return False


load_dotenv()

required = ["PYTHON", "WORKDIR"]
missing = [v for v in required if v not in os.environ]
if missing:
    fail(f"Saknar miljövariabler: {', '.join(missing)} (lägg till i .env)")

py = os.environ["PYTHON"]
workdir = os.environ["WORKDIR"]
env = os.environ.get("CONDA_ENV", "").strip()  # tom = bare metal

if not Path(py).exists():
    fail(f"PYTHON: '{py}' finns inte på disk! Kontrollera sökvägen i .env.")

if not Path(workdir).exists():
    fail(f"WORKDIR: '{workdir}' finns inte på disk! Kontrollera sökvägen i .env.")

if env:
    if not conda_env_exists(env):
        fail(f"Miljön ENV='{env}' verkar inte finnas (kolla med 'conda env list').")
    exec_start = f"{py} run -n {env} python3 -u {workdir}/servera.py"
    log(f"✅ Använder conda-miljö: {env}")
else:
    exec_start = f"{py} {workdir}/servera.py"
    log("✅ Använder systemets Python (ingen conda-miljö vald)")

service = f"""[Unit]
Description=Starta Sommar-feed servera.py (SSL, auto-reload)
After=network.target

[Service]
Type=simple
WorkingDirectory={workdir}
Environment=PYTHONUNBUFFERED=1
ExecStart={exec_start}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target

"""

with open("sommar-server.service", "w") as f:
    f.write(service)

log("✅ Skapade sommar-server.service!")
