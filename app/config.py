from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    database_url: str = "sqlite:///./pet_medical_records.db"
    upload_dir: Path | str = Path("uploads")

    def __post_init__(self) -> None:
        self.upload_dir = Path(self.upload_dir)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv(
                "PET_MEDICAL_RECORDS_DATABASE_URL",
                "sqlite:///./pet_medical_records.db",
            ),
            upload_dir=os.getenv("PET_MEDICAL_RECORDS_UPLOAD_DIR", "uploads"),
        )
