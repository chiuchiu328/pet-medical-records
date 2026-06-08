from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(file_name: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", Path(file_name).name).strip("._")
    return cleaned or "upload"


def owner_directory(upload_dir: Path, owner_type: str, owner_id: int) -> Path:
    return upload_dir / owner_type / str(owner_id)


def store_fileobj(upload_dir: Path, owner_type: str, owner_id: int, file_name: str, fileobj) -> Path:
    directory = owner_directory(upload_dir, owner_type, owner_id)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{uuid4().hex}_{sanitize_filename(file_name)}"
    with destination.open("wb") as output:
        shutil.copyfileobj(fileobj, output)
    return destination


def copy_local_file(upload_dir: Path, owner_type: str, owner_id: int, source_path: Path) -> Path:
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"File does not exist: {source_path}")
    with source_path.open("rb") as source:
        return store_fileobj(upload_dir, owner_type, owner_id, source_path.name, source)
