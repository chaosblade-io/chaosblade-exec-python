# Copyright 2025 The ChaosBlade Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""HTTP Server - lightweight HTTP server for ChaosBlade agent management.

Uses stdlib http.server, runs in a daemon thread to avoid interfering
with the target application. Supports both GET and POST requests.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Response
from chaosblade.service.dispatch import DispatchService

logger = logging.getLogger(__name__)


class _ChaosBladeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ChaosBlade management commands."""

    # Class-level reference, set by start_server()
    dispatch_service: DispatchService

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests: parse URL query params and dispatch."""
        parsed = urlparse(self.path)
        command = parsed.path.lstrip("/")
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        request = Request(params)
        response = self.dispatch_service.dispatch(command, request)
        self._send_response(response)

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests: parse JSON body (merged with query params)."""
        parsed = urlparse(self.path)
        command = parsed.path.lstrip("/")

        # Start with query params
        params: dict[str, str] = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        # Read and parse JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                body_params = json.loads(body.decode("utf-8"))
                if isinstance(body_params, dict):
                    # Merge body params (body takes priority over query)
                    for k, v in body_params.items():
                        params[k] = str(v) if not isinstance(v, str) else v
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.debug("Failed to parse POST body as JSON")

        request = Request(params)
        response = self.dispatch_service.dispatch(command, request)
        self._send_response(response)

    def _send_response(self, response: Response) -> None:
        """Send HTTP 200 with JSON body (business code in JSON)."""
        body = response.to_json().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format: str, *args: any) -> None:
        """Suppress default HTTP access logs."""
        logger.debug("HTTP: %s", format % args)


def start_server(port: int, host: str = "127.0.0.1") -> HTTPServer:
    """Start the ChaosBlade HTTP management server in a daemon thread.

    Args:
        port: Port to listen on. Use 0 for OS-assigned port.
        host: Host to bind to. Default is localhost only.

    Returns:
        The HTTPServer instance (call .shutdown() to stop).
    """
    dispatch = DispatchService()
    _ChaosBladeHTTPHandler.dispatch_service = dispatch

    server = HTTPServer((host, port), _ChaosBladeHTTPHandler)
    actual_port = server.server_address[1]

    thread = threading.Thread(
        target=server.serve_forever,
        name="chaosblade-http-server",
        daemon=True,
    )
    thread.start()

    logger.info("ChaosBlade agent HTTP server started on %s:%d", host, actual_port)
    return server
