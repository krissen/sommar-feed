import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 443
FILE = Path("podcast.xml")
CERT_FILE = Path("ssl/fullchain.pem")
KEY_FILE = Path("ssl/privkey.pem")

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
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    httpd = HTTPServer(("0.0.0.0", PORT), SimpleXMLHandler)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"Serving https://0.0.0.0:{PORT}/podcast.xml with SSL")
    httpd.serve_forever()

