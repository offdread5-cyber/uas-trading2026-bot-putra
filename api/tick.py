import json
import os
import hmac
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Melindungi endpoint menggunakan CRON_SECRET
        secret = os.environ.get("CRON_SECRET")

        if not secret:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":"CRON_SECRET belum diatur"}')
            return

        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {secret}"

        if not hmac.compare_digest(auth, expected):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"Unauthorized"}')
            return

        # Respons awal untuk menguji endpoint
        response = {
            "status": "success",
            "message": "Vercel trading bot endpoint aktif",
            "endpoint": "/api/tick"
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
