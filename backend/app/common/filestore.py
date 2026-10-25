import os
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename


ALLOWED_SIGNATURES = {
    ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ".pdf": lambda data: data.startswith(b"%PDF-"),
}

DEFAULT_MAX_SIZE_BYTES = 10 * 1024 * 1024


class FileStoreError(ValueError):
    """Raised when a document cannot safely be stored."""


class FileStore:
    """Store validated documents in a local directory."""

    def __init__(self, root=None, max_size_bytes=None):
        default_root = Path(__file__).resolve().parents[2] / "uploads"
        self.root = Path(
            root or os.environ.get("UPLOAD_FOLDER", default_root)
        ).resolve()
        self.max_size_bytes = max_size_bytes or int(
            os.environ.get(
                "MAX_DOCUMENT_SIZE_BYTES",
                DEFAULT_MAX_SIZE_BYTES,
            )
        )

    def save(self, file_storage):
        original_name = secure_filename(file_storage.filename or "")
        extension = Path(original_name).suffix.lower()

        if not original_name or extension not in ALLOWED_SIGNATURES:
            raise FileStoreError(
                "Unsupported file type. Allowed types: JPG, JPEG, PNG, PDF."
            )

        content = file_storage.stream.read(self.max_size_bytes + 1)

        if not content:
            raise FileStoreError("The uploaded file is empty.")

        if len(content) > self.max_size_bytes:
            raise FileStoreError("The uploaded file exceeds the size limit.")

        if not ALLOWED_SIGNATURES[extension](content):
            raise FileStoreError(
                "The file content does not match its extension."
            )

        self.root.mkdir(parents=True, exist_ok=True)

        stored_name = f"{uuid.uuid4().hex}{extension}"
        destination = (self.root / stored_name).resolve()

        if destination.parent != self.root:
            raise FileStoreError("Invalid storage path.")

        destination.write_bytes(content)

        return {
            "stored_name": stored_name,
            "relative_path": stored_name,
            "original_name": original_name,
            "size_bytes": len(content),
            "content_type": {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".pdf": "application/pdf",
            }[extension],
        }

    def open(self, relative_path):
        # Only accept a generated filename, never an arbitrary filesystem path.
        if not relative_path or Path(relative_path).name != relative_path:
            raise FileStoreError("Invalid stored file path.")

        path = (self.root / relative_path).resolve()

        if path.parent != self.root or not path.is_file():
            raise FileNotFoundError("Stored document not found.")

        return path.open("rb")

    def delete(self, relative_path):
        if not relative_path or Path(relative_path).name != relative_path:
            raise FileStoreError("Invalid stored file path.")

        path = (self.root / relative_path).resolve()

        if path.parent != self.root:
            raise FileStoreError("Invalid stored file path.")

        path.unlink(missing_ok=True)
