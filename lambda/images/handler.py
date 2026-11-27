"""Store an image in S3 and its key in RDS.

The client uploads bytes with a presigned URL. This function only handles
metadata, then checks the object exists before writing the database row.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

MAX_BYTES = 20 * 1024 * 1024
URL_TTL = 60
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
ID_RE = re.compile(r"^[0-9a-f]{32}$")
TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS images (
  id CHAR(32) NOT NULL PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  content_type VARCHAR(64) NOT NULL,
  s3_key VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
_schema_ready = False


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    """Create, finish, list, read, rename, or delete an image record."""
    try:
        return _dispatch(event or {})
    except ValueError as exc:
        return _response(400, {"ok": False, "error": str(exc)})


def _dispatch(event: dict[str, Any]) -> dict[str, Any]:
    method = _method(event)
    parts = [part for part in _path(event).split("/") if part]
    if parts == ["images"] and method == "POST":
        return _start(event)
    if parts == ["images"] and method == "GET":
        return _list()
    if len(parts) == 3 and parts[0] == "images" and parts[2] == "complete" and method == "POST":
        return _complete(event, parts[1])
    if len(parts) == 2 and parts[0] == "images":
        image_id = _valid_id(parts[1])
        if method == "GET":
            return _read(image_id)
        if method == "PATCH":
            return _rename(event, image_id)
        if method == "DELETE":
            return _delete(image_id)
    return _response(404, {"ok": False, "error": "unknown route"})


def _start(event: dict[str, Any]) -> dict[str, Any]:
    name, content_type = _meta(event)
    image_id = uuid.uuid4().hex
    key = f"images/{image_id}.{TYPES[content_type]}"
    bucket = os.environ["IMAGE_BUCKET"]
    upload_url = _s3().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=URL_TTL,
    )
    return _response(
        201,
        {
            "ok": True,
            "service": "gha-lambda-practice",
            "id": image_id,
            "name": name,
            "content_type": content_type,
            "s3_key": key,
            "upload_url": upload_url,
            "expires_in": URL_TTL,
        },
    )


def _complete(event: dict[str, Any], image_id: str) -> dict[str, Any]:
    image_id = _valid_id(image_id)
    name, content_type = _meta(event)
    key = f"images/{image_id}.{TYPES[content_type]}"
    if _select(image_id) is not None:
        return _response(409, {"ok": False, "error": "image already exists"})
    bucket = os.environ["IMAGE_BUCKET"]
    _require_object(bucket, key, content_type)
    _insert(image_id, name, content_type, key)
    return _response(201, _record(image_id, name, content_type, key, bucket))


def _list() -> dict[str, Any]:
    connection = _connect()
    try:
        _ensure_schema(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, content_type, s3_key, created_at
                FROM images
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
            rows = cursor.fetchall()
    finally:
        connection.close()
    images = []
    for row in rows:
        created = row["created_at"]
        images.append(
            {
                "id": row["id"],
                "name": row["name"],
                "content_type": row["content_type"],
                "s3_key": row["s3_key"],
                "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
            }
        )
    return _response(200, {"ok": True, "service": "gha-lambda-practice", "images": images})


def _read(image_id: str) -> dict[str, Any]:
    row = _select(image_id)
    if row is None:
        return _response(404, {"ok": False, "error": "image not found"})
    bucket = os.environ["IMAGE_BUCKET"]
    return _response(200, _record(row["id"], row["name"], row["content_type"], row["s3_key"], bucket))


def _rename(event: dict[str, Any], image_id: str) -> dict[str, Any]:
    name = _name(_json_body(event))
    row = _select(image_id)
    if row is None:
        return _response(404, {"ok": False, "error": "image not found"})
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE images SET name = %s WHERE id = %s", (name, image_id))
    finally:
        connection.close()
    bucket = os.environ["IMAGE_BUCKET"]
    return _response(200, _record(image_id, name, row["content_type"], row["s3_key"], bucket))


def _delete(image_id: str) -> dict[str, Any]:
    row = _select(image_id)
    if row is None:
        return _response(404, {"ok": False, "error": "image not found"})
    _s3().delete_object(Bucket=os.environ["IMAGE_BUCKET"], Key=row["s3_key"])
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM images WHERE id = %s", (image_id,))
    finally:
        connection.close()
    return _response(200, {"ok": True, "service": "gha-lambda-practice", "id": image_id, "deleted": True})


def _require_object(bucket: str, key: str, content_type: str) -> None:
    from botocore.exceptions import ClientError

    try:
        head = _s3().head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise ValueError("upload the file to S3 before complete") from exc
        raise
    size = int(head.get("ContentLength", 0))
    actual = str(head.get("ContentType", "")).split(";", 1)[0].strip().lower()
    if size < 1 or size > MAX_BYTES or actual != content_type:
        _s3().delete_object(Bucket=bucket, Key=key)
        raise ValueError("file must match content_type and be between 1 byte and 20 MB")


def _meta(event: dict[str, Any]) -> tuple[str, str]:
    payload = _json_body(event)
    content_type = str(payload.get("content_type", "")).strip().lower()
    if content_type not in TYPES:
        raise ValueError("content_type must be image/jpeg, image/png, image/gif, or image/webp")
    return _name(payload), content_type


def _name(payload: dict[str, Any]) -> str:
    name = str(payload.get("name", "")).strip()
    if not NAME_RE.fullmatch(name):
        raise ValueError("name must be 1-64 characters: letters, numbers, space, dot, underscore, hyphen")
    return name


def _valid_id(image_id: str) -> str:
    if not ID_RE.fullmatch(image_id):
        raise ValueError("id must be 32 hex characters")
    return image_id


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if not isinstance(raw, str) or raw == "":
        raise ValueError("JSON body is required")
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError("request body is not valid base64") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("body must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")
    return payload


def _insert(image_id: str, name: str, content_type: str, key: str) -> None:
    connection = _connect()
    try:
        _ensure_schema(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO images (id, name, content_type, s3_key) VALUES (%s, %s, %s, %s)",
                (image_id, name, content_type, key),
            )
    finally:
        connection.close()


def _select(image_id: str) -> dict[str, Any] | None:
    connection = _connect()
    try:
        _ensure_schema(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, content_type, s3_key FROM images WHERE id = %s",
                (image_id,),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def _ensure_schema(connection: Any) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with connection.cursor() as cursor:
        cursor.execute(CREATE_TABLE)
    _schema_ready = True


def _connect() -> Any:
    import pymysql
    from pymysql.cursors import DictCursor

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        ssl={"ca": str(Path(__file__).with_name("global-bundle.pem"))},
    )


def _s3() -> Any:
    import boto3
    from botocore.config import Config

    if not hasattr(_s3, "client"):
        _s3.client = boto3.client(
            "s3",
            config=Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
    return _s3.client


def _record(image_id: str, name: str, content_type: str, key: str, bucket: str) -> dict[str, Any]:
    url = _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=URL_TTL,
    )
    return {
        "ok": True,
        "service": "gha-lambda-practice",
        "id": image_id,
        "name": name,
        "content_type": content_type,
        "s3_key": key,
        "url": url,
    }


def _method(event: dict[str, Any]) -> str:
    request = event.get("requestContext") or {}
    http = request.get("http") if isinstance(request, dict) else {}
    nested = http.get("method") if isinstance(http, dict) else ""
    return str(event.get("httpMethod") or nested or "").upper()


def _path(event: dict[str, Any]) -> str:
    raw = str(event.get("path") or event.get("rawPath") or "")
    path = raw.split("?", 1)[0]
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }
