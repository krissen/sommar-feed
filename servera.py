import ssl
import threading
import subprocess
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 443
FILE = Path("podcast.xml")
CERT_FILE = Path("ssl/fullchain.pem")
KEY_FILE = Path("ssl/privkey.pem")

def run_sommar_script():
    print("Kör sommar.py för att generera podcast.xml …")
    # Kör i samma mapp och fånga eventuella felutskrifter
    try:
        subprocess.run(["python3", "sommar.py"], check=True)
    except Exception as e:
        print(f"Fel vid körning av sommar.py: {e}")

def scheduler():
    """Schemalägg körning 07:15 och 19:15 varje dag."""
    while True:
        now = datetime.now()
        # Nästa tidpunkt (07:15 eller 19:15)
        next_times = [
            now.replace(hour=7, minute=15, second=0, microsecond=0),
            now.replace(hour=13, minute=00, second=0, microsecond=0),
            now.replace(hour=19, minute=00, second=0, microsecond=0)
        ]
        # Om redan passerat, addera en dag
        next_times = [t if t > now else t + timedelta(days=1) for t in next_times]
        next_run = min(next_times)
        wait_seconds = (next_run - now).total_seconds()
        print(f"Nästa körning: {next_run} ({wait_seconds/3600:.2f} timmar kvar)")
        time.sleep(wait_seconds)
        run_sommar_script()

class SimpleXMLHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/podcast.xml":
            if FILE.exists():
                self.send_response(200)
                self.send_header("Content-type", "application/xml; charset=utf-8")
                self.end_headers()
                self.wfile.write(FILE.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found.")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Invalid path.")

if __name__ == "__main__":
    # Starta bakgrundstråd för schemaläggning
    t = threading.Thread(target=scheduler, daemon=True)
    t.start()

    # Starta servern (main thread)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    httpd = HTTPServer(("0.0.0.0", PORT), SimpleXMLHandler)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"Serving https://0.0.0.0:{PORT}/podcast.xml with SSL")
    httpd.serve_forever()

