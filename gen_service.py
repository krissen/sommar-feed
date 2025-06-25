#!/usr/bin/env python3
import os
import sys

from dotenv import load_dotenv

load_dotenv()

required = ["USER", "HOME", "ENV", "PYTHON", "WORKDIR"]
missing = [v for v in required if v not in os.environ]
if missing:
    print(f"❌ Saknar miljövariabler: {', '.join(missing)}")
    sys.exit(1)

user = os.environ["USER"]
env = os.environ["ENV"]
py = os.environ["PYTHON"]
workdir = os.environ["WORKDIR"]

service = f"""[Unit]
Description=Starta Sommar-feed servera.py (SSL, auto-reload)
After=network.target

[Service]
Type=simple
WorkingDirectory={workdir}
Environment=PYTHONUNBUFFERED=1
ExecStart={py} run -n {env} python3 -u {workdir}/servera.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target

"""

with open("sommar-server.service", "w") as f:
    f.write(service)

print("✅ Skapade sommar-server.service!")
