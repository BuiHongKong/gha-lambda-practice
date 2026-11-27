"""Validation tests. They stop before RDS and S3."""

from __future__ import annotations

import json
import unittest

import handler


def _event(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload)
    return {"httpMethod": method, "path": path, "body": body}


class HandlerTest(unittest.TestCase):
    def test_unknown_route(self) -> None:
        result = handler.handler(_event("GET", "/hello"), None)
        self.assertEqual(result["statusCode"], 404)

    def test_missing_body(self) -> None:
        result = handler.handler(_event("POST", "/images"), None)
        self.assertEqual(result["statusCode"], 400)

    def test_rejects_non_image(self) -> None:
        result = handler.handler(_event("POST", "/images", {"name": "cat", "content_type": "text/plain"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_rejects_bad_name(self) -> None:
        result = handler.handler(_event("POST", "/images", {"name": "../cat", "content_type": "image/jpeg"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_rejects_bad_id(self) -> None:
        for method, path in (
            ("GET", "/images/not-an-id"),
            ("PATCH", "/images/not-an-id"),
            ("DELETE", "/images/not-an-id"),
            ("POST", "/images/not-an-id/complete"),
        ):
            with self.subTest(path=path):
                result = handler.handler(_event(method, path, {"name": "cat", "content_type": "image/jpeg"}), None)
                self.assertEqual(result["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
