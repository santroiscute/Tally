from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXTRACT_DIR = DATA_DIR / "extracted"
LOG_DIR = BASE_DIR / "logs"

SUPPORTED_PDF_SUFFIXES = {".pdf"}
SUPPORTED_ARCHIVE_SUFFIXES = {".zip"}

DEFAULT_TALLY_VOUCHER_TYPE = "Journal"


def ensure_directories() -> None:
    for path in (DATA_DIR, UPLOAD_DIR, EXTRACT_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
