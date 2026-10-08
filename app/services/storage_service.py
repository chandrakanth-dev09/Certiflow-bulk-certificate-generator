from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Iterable

from app.core.config import BASE_DIR, settings


class StorageService:
    def __init__(self, storage_dir: str | None = None) -> None:
        self.root_dir = Path(storage_dir or settings.STORAGE_DIR)
        if not self.root_dir.is_absolute():
            self.root_dir = BASE_DIR / self.root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def resolve_job_dir(self, job_id: str) -> Path:
        job_dir = self.root_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def save_pdf(self, job_id: str, certificate_id: str, pdf_bytes: bytes, certificate_number: str) -> str:
        job_dir = self.resolve_job_dir(job_id)
        target = job_dir / f"{certificate_id}.pdf"
        target.write_bytes(pdf_bytes)
        return str(target)

    @staticmethod
    def _safe_filename(value: str) -> str:
        sanitized = os.path.basename(value).replace("/", "_").replace("\\", "_")
        return sanitized.strip() or "certificate"

    def exists(self, file_path: str) -> bool:
        return Path(file_path).exists()

    def get_path_for_certificate(self, job_id: str, certificate_id: str) -> Path:
        return self.resolve_job_dir(job_id) / f"{certificate_id}.pdf"

    def build_zip_for_completed_certificates(self, job_id: str, certificates: Iterable[object]) -> str:
        job_dir = self.resolve_job_dir(job_id)
        archive_path = job_dir / f"{job_id}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for certificate in certificates:
                file_path = Path(certificate.file_path)
                if file_path.exists():
                    zf.write(file_path, arcname=f"certificates/{file_path.name}")
        return str(archive_path)
