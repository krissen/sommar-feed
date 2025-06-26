import os
import signal
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv

LOG_FILE = Path("server.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
    except Exception:
        pass

def handle_sigterm(signum, frame):
    log("🛑 Avbryter servering (SIGTERM) – stänger ner servern ...")
    httpd.server_close()
    log("👋 Servern är nu avstängd.")
    exit(0)



def check_ssl_files(cert_file, key_file):
    missing = False
    if not cert_file.exists():
        log(f"❌ CERT_FILE saknas: {cert_file}")
        missing = True
    if not key_file.exists():
        log(f"❌ KEY_FILE saknas: {key_file}")
        missing = True
    if missing:
        log("⛔️ SSL-filer saknas – kan inte starta servern!")
        return False
    else:
        log("✅ Alla SSL-filer finns.")
        return True

def run_sommar_script():
    log("Kör sommar.py för att generera podcast.xml …")
    try:
        res = subprocess.run(
            ["python3", "sommar.py"],
            check=True,
            capture_output=True,
            text=True,
        )
        if res.stdout:
            log(res.stdout)
        if res.stderr:
            log("STDERR: " + res.stderr)
    except Exception as e:
        log(f"Fel vid körning av sommar.py: {e}")


def scheduler():
    """Schemalägg körning."""
    while True:
        now = datetime.now()
        next_times = [
            now.replace(hour=7, minute=5, second=0, microsecond=0),
            now.replace(hour=13, minute=0, second=0, microsecond=0),
            now.replace(hour=19, minute=0, second=0, microsecond=0),
        ]
        # Om redan passerat, addera en dag
        next_times = [t if t > now else t + timedelta(days=1) for t in next_times]
        next_run = min(next_times)
        wait_seconds = (next_run - now).total_seconds()
        log(f"⏰ Nästa körning: {next_run} ({wait_seconds/3600:.2f} timmar kvar)")
        time.sleep(wait_seconds)
        run_sommar_script()


class SimpleXMLHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/podcast.xml":
            if RSS_FILE.exists():
                self.send_response(200)
                self.send_header("Content-type", "application/xml; charset=utf-8")
                self.end_headers()
                self.wfile.write(RSS_FILE.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found.")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Invalid path.")

    def log_message(self, format, *args):
        # Skriv till din egen log istället för stderr
        log(f"{self.client_address[0]} - {format % args}")


if __name__ == "__main__":
    load_dotenv()

    # Ställ in port
    port_env = os.environ.get("PORT")
    PORT = if port_env else 443  # Standardport om inte angiven

    # Läs in sökvägar till certifikat från .env
    cert_env = os.environ.get("SSL_CHAIN")
    key_env = os.environ.get("SSL_KEY")
    CERT_FILE = Path(cert_env) if cert_env else Path("ssl/fullchain.pem")
    KEY_FILE = Path(key_env) if key_env else Path("ssl/privkey.pem")

    # Ställ in sökväg till RSS-filen
    rss_env = os.environ.get("RSS_FILE")
    RSS_FILE = if rss_env else Path("podcast.xml")

    # Kolla vi har SSL -filerna
    if not check_ssl_files(CERT_FILE, KEY_FILE):
        exit(1)

    # Starta bakgrundstråd för schemaläggning
    t = threading.Thread(target=scheduler, daemon=True)
    t.start()

    # Starta servern (main thread)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    httpd = HTTPServer(("0.0.0.0", PORT), SimpleXMLHandler)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    log(f"🌐 Serving https://0.0.0.0:{PORT}/podcast.xml with SSL")

    # Registrera signalhanteraren
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("🛑 Avbryter servering (Ctrl-C) – stänger ner servern ...")
        httpd.server_close()
        log("👋 Servern är nu avstängd.")

