"""File storage for listing photos.

Files live on local disk under settings.media_dir. Everything goes through get_storage(), so
S3-compatible storage can replace LocalStorage later without touching the routes.
Nothing here is public: the API serves files only to signed-in users of the same company.
"""
from pathlib import Path

from app.config import settings

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_LISTING = 10

_SERVER_DIR = Path(__file__).resolve().parents[2]  # D:\gharmind\server


def detect_image(data: bytes) -> tuple[str, str] | None:
    """(content type, extension) judged from the file's own bytes, or None if it is not a
    JPEG, PNG or WebP photo. The name and the browser's claimed type are never trusted.
    SVG is deliberately not allowed (it can carry scripts)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:  # blocks "../" tricks
            raise ValueError("bad storage key")
        return p

    def save(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)  # a half-written file is never visible under the real name

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass


def get_storage() -> LocalStorage:
    root = Path(settings.media_dir)
    if not root.is_absolute():
        root = _SERVER_DIR / root
    return LocalStorage(root)