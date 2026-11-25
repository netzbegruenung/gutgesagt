"""Minimal stand-in for the Keycloak admin API used by KeycloakKonten.konto_anlegen.
Assigns account ids from IDS in order; logs every request (no real mail)."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

IDS = os.environ.get("IDS", "teams-neu-1,teams-neu-2,teams-neu-3").split(",")
state = {"next": 0, "emails": {}, "log": []}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        if self.path == "/_log":
            return self._send(200, state)
        self._send(200, [])

    def do_POST(self):
        b = self._body()
        state["log"].append(["POST", self.path])
        if self.path.endswith("/protocol/openid-connect/token"):
            return self._send(200, {"access_token": "fake", "expires_in": 300})
        if self.path.endswith("/users"):
            konto = json.loads(b or b"{}")
            email = konto.get("email")
            if email in state["emails"]:
                return self._send(409, {"errorMessage": "exists"})
            kid = IDS[state["next"]]
            state["next"] += 1
            state["emails"][email] = kid
            return self._send(
                201, None, {"Location": f"http://fakekc{self.path}/{kid}"}
            )
        self._send(404, {})

    def do_PUT(self):
        self._body()
        state["log"].append(["PUT", self.path])
        self._send(204)

    def do_DELETE(self):
        state["log"].append(["DELETE", self.path])
        self._send(204)


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
