#!/usr/bin/env python3
"""Local API Gateway console. Credentials stay in this process."""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8766"))
MAX_BODY = 2_000_000
MAX_UPLOAD = 20 * 1024 * 1024
S3_HOST = re.compile(r"^[a-z0-9.-]+\.s3\.ap-southeast-1\.amazonaws\.com$", re.IGNORECASE)
S3_PATH = re.compile(r"^/images/[0-9a-f]{32}\.(jpg|png|gif|webp)$", re.IGNORECASE)
UPLOAD_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PAGE = Path(__file__).with_name("index.html").read_bytes()
EXECUTE_API = re.compile(
    r"^https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com(?::\d+)?(?:/.*)?$",
    re.IGNORECASE,
)


class NoRedirect(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):  # noqa: ARG002
        return response

    https_response = http_response


class NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


OPENER = urllib.request.build_opener(NoRedirect, NoFollow)
_SESSION_LOCK = threading.Lock()
_SESSION: dict[str, object] | None = None


def _check_upload_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not S3_HOST.fullmatch(parts.hostname or ""):
        raise ValueError("Upload URL must be the lab image bucket in ap-southeast-1")
    if not S3_PATH.fullmatch(parts.path or ""):
        raise ValueError("Upload URL must target images/{id}.ext")
    query = parse_qs(parts.query)
    if "X-Amz-Algorithm" not in query or "X-Amz-Signature" not in query:
        raise ValueError("Upload URL must already be signed")


def region_of(url: str) -> str:
    host = urlsplit(url).hostname or ""
    parts = host.split(".")
    try:
        index = parts.index("execute-api")
    except ValueError as exc:
        raise ValueError("URL must be an API Gateway execute-api host") from exc
    return parts[index + 1]


def _aws_json(args: list[str]) -> dict[str, object]:
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=40, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("Không thấy lệnh aws trong process này.") from exc
    if completed.returncode != 0:
        lines = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        raise RuntimeError(lines[-1][:300] if lines else "AWS CLI failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AWS CLI không trả JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("AWS CLI không trả JSON object.")
    return payload


def _parse_expiry(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def session_view() -> dict[str, object]:
    with _SESSION_LOCK:
        if _SESSION is None:
            return {"ok": False}
        expires = _SESSION.get("expires")
        if not isinstance(expires, datetime) or expires <= datetime.now(timezone.utc):
            return {"ok": False}
        return {
            "ok": True,
            "account": _SESSION.get("account", ""),
            "arn": _SESSION.get("arn", ""),
            "expires": expires.isoformat(),
        }


def refresh_session() -> dict[str, object]:
    global _SESSION
    try:
        identity = _aws_json(["aws", "sts", "get-caller-identity", "--output", "json"])
        exported = _aws_json(["aws", "configure", "export-credentials", "--format", "process"])
        access_key = str(exported.get("AccessKeyId", ""))
        secret_key = str(exported.get("SecretAccessKey", ""))
        token = str(exported.get("SessionToken", ""))
        if not access_key or not secret_key or not token:
            raise RuntimeError("Phiên không có credential ngắn hạn.")
        expiry_raw = exported.get("Expiration")
        expires = _parse_expiry(str(expiry_raw)) if expiry_raw else datetime.now(timezone.utc)
        with _SESSION_LOCK:
            _SESSION = {
                "access_key": access_key,
                "secret_key": secret_key,
                "token": token,
                "expires": expires,
                "account": str(identity.get("Account", "")),
                "arn": str(identity.get("Arn", "")),
            }
    except Exception:
        with _SESSION_LOCK:
            _SESSION = None
        raise
    return session_view()


def _frozen_credentials() -> object:
    from botocore.credentials import Credentials

    with _SESSION_LOCK:
        if _SESSION is None:
            raise RuntimeError("Chưa có phiên. Bấm Xin credential.")
        expires = _SESSION.get("expires")
        if not isinstance(expires, datetime) or expires <= datetime.now(timezone.utc):
            raise RuntimeError("Phiên đã hết hạn. Bấm Xin credential lại.")
        return Credentials(
            str(_SESSION["access_key"]),
            str(_SESSION["secret_key"]),
            str(_SESSION["token"]),
        ).get_frozen_credentials()


def sign_headers(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict[str, str]:
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    request = AWSRequest(method=method, url=url, data=body, headers=headers)
    SigV4Auth(_frozen_credentials(), "execute-api", region_of(url)).add_auth(request)
    return {key: value for key, value in request.headers.items()}


def sign_websocket(url: str) -> str:
    from botocore.auth import SigV4QueryAuth
    from botocore.awsrequest import AWSRequest

    if not url.lower().startswith("wss://"):
        raise ValueError("WebSocket URL must start with wss://")
    https_url = "https://" + url[len("wss://") :]
    if not EXECUTE_API.match(https_url.split("?", 1)[0]):
        raise ValueError("WebSocket URL must be an API Gateway execute-api host")
    request = AWSRequest(method="GET", url=https_url)
    SigV4QueryAuth(_frozen_credentials(), "execute-api", region_of(https_url), expires=60).add_auth(request)
    return "wss://" + request.url[len("https://") :]


def parse_headers(lines: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Header must look like Name: value ({line!r})")
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()
    return headers


def send_upstream(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict[str, object]:
    if not EXECUTE_API.match(url.split("?", 1)[0]):
        raise ValueError("URL must be https://{api-id}.execute-api.{region}.amazonaws.com/...")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with OPENER.open(request, timeout=35) as response:
            payload = response.read(MAX_BODY + 1)
            status = response.status
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as error:
        payload = error.read(MAX_BODY + 1)
        status = error.code
        response_headers = dict(error.headers.items())
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    truncated = len(payload) > MAX_BODY
    text = payload[:MAX_BODY].decode("utf-8", errors="replace")
    return {
        "status": status,
        "elapsed_ms": elapsed_ms,
        "headers": response_headers,
        "body": text,
        "truncated": truncated,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/session":
            self._json(200, session_view())
            return
        if path != "/":
            self._json(404, {"error": "Not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/put-object":
                self._json(200, self._put_object())
                return
            if path == "/api/session":
                self._json(200, refresh_session())
                return
            payload = self._read_json()
            if path == "/api/send":
                self._json(200, self._send(payload))
            elif path == "/api/sign-websocket":
                self._json(200, {"url": sign_websocket(str(payload.get("url", "")))})
            else:
                self._json(404, {"error": "Not found"})
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def _send(self, payload: dict[str, object]) -> dict[str, object]:
        method = str(payload.get("method", "GET")).upper()
        url = str(payload.get("url", "")).strip()
        header_lines = payload.get("headers") or []
        if not isinstance(header_lines, list):
            raise ValueError("headers must be a list of lines")
        headers = parse_headers([str(line) for line in header_lines])
        raw_body = payload.get("body")
        body = None if raw_body in (None, "") or method == "GET" else str(raw_body).encode("utf-8")
        if body is not None and "Content-Type" not in headers and "content-type" not in {key.lower() for key in headers}:
            headers["Content-Type"] = "application/json"
        if payload.get("sign"):
            headers = sign_headers(method, url, headers, body)
        return send_upstream(method, url, headers, body)

    def _put_object(self) -> dict[str, object]:
        url = self.headers.get("x-upload-url", "").strip()
        content_type = self.headers.get("x-upload-content-type", "").strip().lower()
        length = int(self.headers.get("Content-Length", "0"))
        if content_type not in UPLOAD_TYPES:
            raise ValueError("content type must be image/jpeg, image/png, image/gif, or image/webp")
        if length < 1 or length > MAX_UPLOAD:
            raise ValueError("image must be between 1 byte and 20 MB")
        _check_upload_url(url)
        body = self.rfile.read(length)
        request = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="PUT")
        started = time.perf_counter()
        try:
            with OPENER.open(request, timeout=60) as response:
                status = response.status
                detail = response.read(1000).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            status = error.code
            detail = error.read(1000).decode("utf-8", errors="replace")
        return {"status": status, "elapsed_ms": int((time.perf_counter() - started) * 1000), "body": detail}

    def _json(self, status: int, payload: dict[str, object]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
