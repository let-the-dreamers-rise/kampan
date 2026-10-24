"""Where clips live: S3 in the cloud, a folder on a laptop. Same three operations."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Protocol

KEY_PATTERN = re.compile(r"^(uploads|samples)/[A-Za-z0-9][A-Za-z0-9._-]{0,120}(/[A-Za-z0-9._-]{1,120})?$")
MAX_UPLOAD_BYTES = 300 * 1024 * 1024


def check_key(key: str) -> str:
    if not isinstance(key, str) or not KEY_PATTERN.match(key) or ".." in key:
        raise ValueError(f"invalid clip key: {key!r}")
    return key


class Storage(Protocol):
    def upload_target(self, key: str, content_type: str) -> dict: ...

    def download(self, key: str, path: Path) -> Path: ...

    def put_file(self, key: str, path: Path, content_type: str) -> None: ...


class S3Storage:
    def __init__(self, bucket: str, client=None) -> None:
        import boto3  # imported lazily so local runs do not need AWS credentials

        self.bucket = bucket
        self.client = client or boto3.client("s3")

    def upload_target(self, key: str, content_type: str) -> dict:
        post = self.client.generate_presigned_post(
            self.bucket, check_key(key), Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, MAX_UPLOAD_BYTES]],
            ExpiresIn=900)
        return {"method": "POST", "url": post["url"], "fields": post["fields"]}

    def download(self, key: str, path: Path) -> Path:
        self.client.download_file(self.bucket, check_key(key), str(path))
        return path

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        self.client.upload_file(str(path), self.bucket, check_key(key), ExtraArgs={"ContentType": content_type})


class LocalStorage:
    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_of(self, key: str) -> Path:
        return self.root / check_key(key)

    def upload_target(self, key: str, content_type: str) -> dict:
        return {"method": "PUT", "url": f"/local-upload/{check_key(key)}", "fields": {}}

    def download(self, key: str, path: Path) -> Path:
        src = self.path_of(key)
        if not src.exists():
            raise FileNotFoundError(key)
        shutil.copyfile(src, path)
        return path

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        dst = self.path_of(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)

    def write_bytes(self, key: str, data: bytes) -> None:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("file too large")
        dst = self.path_of(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)


def storage_from_env() -> Storage:
    bucket = os.environ.get("KAMPAN_BUCKET")
    if bucket:
        return S3Storage(bucket)
    return LocalStorage(os.environ.get("KAMPAN_LOCAL_DIR", "out/storage"))
