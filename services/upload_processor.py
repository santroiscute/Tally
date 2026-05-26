from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO, Iterable

from config import EXTRACT_DIR, SUPPORTED_ARCHIVE_SUFFIXES, SUPPORTED_PDF_SUFFIXES, UPLOAD_DIR


class UploadProcessor:
    def save_uploaded_file(self, uploaded_file: BinaryIO, file_name: str) -> Path:
        target = UPLOAD_DIR / file_name
        with target.open("wb") as fh:
            shutil.copyfileobj(uploaded_file, fh)
        return target

    def collect_pdfs_from_path(self, path_text: str) -> list[Path]:
        path = Path(path_text).expanduser()
        if not path.exists():
            raise ValueError("The provided path does not exist on the server running Streamlit.")
        if path.is_file():
            return self.collect_pdfs([path])
        return sorted(path.rglob("*.pdf"))

    def collect_pdfs(self, paths: Iterable[Path]) -> list[Path]:
        pdfs: list[Path] = []
        for path in paths:
            suffix = path.suffix.lower()
            if suffix in SUPPORTED_PDF_SUFFIXES:
                pdfs.append(path)
            elif suffix in SUPPORTED_ARCHIVE_SUFFIXES:
                pdfs.extend(self._extract_zip(path))
        return pdfs

    @staticmethod
    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _extract_zip(path: Path) -> list[Path]:
        target_dir = EXTRACT_DIR / path.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(target_dir)
        return sorted(target_dir.rglob("*.pdf"))
