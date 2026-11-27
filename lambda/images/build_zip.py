#!/usr/bin/env python3
"""Build the image Lambda zip. Stdout is a JSON object for Terraform."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT.parents[1] / "terraform" / "lab" / "build"
PACKAGE = BUILD / "package"
CA_URL = "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
CA_CACHE = BUILD / "global-bundle.pem"


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    _install()
    shutil.copyfile(ROOT / "handler.py", PACKAGE / "handler.py")
    _ca_bundle()
    filename = BUILD / "images.zip"
    _zip(PACKAGE, filename)
    digest = base64.b64encode(hashlib.sha256(filename.read_bytes()).digest()).decode("ascii")
    json.dump({"filename": str(filename), "source_code_hash": digest}, sys.stdout)


def _install() -> None:
    requirements = (ROOT / "requirements.txt").read_bytes()
    stamp = BUILD / "requirements.sha256"
    digest = hashlib.sha256(requirements).hexdigest()
    if (PACKAGE / "pymysql").is_dir() and stamp.is_file() and stamp.read_text(encoding="utf-8") == digest:
        return
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "-r",
            str(ROOT / "requirements.txt"),
            "-t",
            str(PACKAGE),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    stamp.write_text(digest, encoding="utf-8")


def _ca_bundle() -> None:
    if not CA_CACHE.is_file():
        urllib.request.urlretrieve(CA_URL, CA_CACHE)
    shutil.copyfile(CA_CACHE, PACKAGE / "global-bundle.pem")


def _zip(source: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    files = sorted(path for path in source.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    with zipfile.ZipFile(destination, "w") as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(source).as_posix())
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


if __name__ == "__main__":
    main()
