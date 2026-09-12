from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import traceback
from pathlib import Path
from typing import Any, Callable

from frontend_json import decode_workspace_state
from json_component import Err as JsonErr

from .service import ApiError, ApplicationService


class ApiHandler(BaseHTTPRequestHandler):
    service = ApplicationService()
    export_dir = Path(__file__).resolve().parents[3] / "data" / "exports"

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(length) if length else b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            raise ApiError(400, "invalid_json", f"Invalid JSON body: {exc}") from exc
        if not isinstance(value, dict):
            raise ApiError(400, "invalid_request", "Request body must be a JSON object")
        return value

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": {"code": "not_found", "message": "Unknown endpoint", "details": []}})

    def do_POST(self) -> None:  # noqa: N802
        routes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "/api/query/snapshot": self.service.snapshot,
            "/api/query/trace": self.service.trace,
            "/api/query/dynamic": self.service.dynamic_analysis,
            "/api/query/compare": self.service.compare,
            "/api/export/result": self.service.result_export,
        }
        try:
            body = self._body()
            if self.path == "/api/workspace/state":
                decoded = decode_workspace_state(body)
                if isinstance(decoded, JsonErr):
                    details = [
                        {
                            "code": getattr(problem.code, "value", str(problem.code)),
                            "message": problem.message,
                            "path": list(problem.path),
                        }
                        for problem in decoded.error
                    ]
                    raise ApiError(422, "invalid_workspace_state", "Workspace state validation failed", tuple(details))
                self.export_dir.mkdir(parents=True, exist_ok=True)
                target = self.export_dir / "workspace-state.json"
                target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
                self._json(200, {"saved": True, "path": str(target)})
                return
            route = routes.get(self.path)
            if route is None:
                raise ApiError(404, "not_found", "Unknown endpoint")
            self._json(200, route(body))
        except ApiError as exc:
            self._json(exc.status, exc.as_json())
        except Exception as exc:  # keep transport errors explicit instead of switching to mock data
            traceback.print_exc()
            self._json(500, {"error": {"code": "internal_error", "message": str(exc) or type(exc).__name__, "details": []}})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[api] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ApiHandler)
    print(f"cosmo backend API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
