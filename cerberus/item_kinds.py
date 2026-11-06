"""Classify vault items into icon kinds and preview modes. Qt-free and side-effect free."""
from __future__ import annotations

from pathlib import PurePath
from typing import Mapping

KINDS = ("text", "link", "image", "pdf", "document", "spreadsheet", "presentation",
         "archive", "code", "audio", "video", "app", "font", "email", "model3d", "file")

_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "image": (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".ico",
              ".svg", ".heic", ".avif"),
    "pdf": (".pdf",),
    "document": (".doc", ".docx", ".odt", ".rtf", ".pages", ".epub"),
    "spreadsheet": (".xls", ".xlsx", ".ods", ".csv", ".tsv", ".numbers"),
    "presentation": (".ppt", ".pptx", ".odp", ".key"),
    "archive": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".iso"),
    "code": (".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".htm", ".css", ".c",
             ".cpp", ".h", ".hpp", ".cs", ".java", ".kt", ".rs", ".go", ".rb", ".php",
             ".sh", ".ps1", ".bat", ".sql", ".yaml", ".yml", ".toml", ".xml", ".ini", ".lua",
             ".swift", ".dart", ".vue"),
    "audio": (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"),
    "video": (".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v"),
    "app": (".exe", ".msi", ".apk", ".appx", ".msix", ".dmg", ".pkg", ".deb", ".rpm",
            ".appimage", ".lnk", ".jar"),
    "font": (".ttf", ".otf", ".woff", ".woff2"),
    "email": (".eml", ".msg", ".mbox"),
    "model3d": (".obj", ".fbx", ".blend", ".stl", ".gltf", ".glb", ".3ds", ".dae", ".usd",
                ".usdz"),
    "text": (".txt", ".md", ".log", ".rst"),
}
_BY_EXTENSION = {ext: kind for kind, exts in _EXTENSIONS.items() for ext in exts}

# Files whose first bytes are shown as text. Never executed, only read.
TEXT_PREVIEW = {".txt", ".md", ".log", ".rst", ".csv", ".tsv", ".json", ".py", ".js", ".ts",
                ".tsx", ".jsx", ".html", ".htm", ".css", ".c", ".cpp", ".h", ".hpp", ".cs",
                ".java", ".kt", ".rs", ".go", ".rb", ".php", ".sh", ".ps1", ".bat", ".sql",
                ".yaml", ".yml", ".toml", ".xml", ".ini", ".lua", ".swift", ".dart", ".vue"}
IMAGE_PREVIEW = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".ico"}
ANIMATED_PREVIEW = {".gif", ".webp"}


# Opening these with the default handler would run code, so the vault never opens them.
RUNNABLE = {".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".pif", ".cpl", ".msc", ".ps1",
            ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".reg", ".lnk",
            ".url", ".jar", ".py", ".pyw", ".appx", ".msix", ".appref-ms", ".application",
            ".gadget", ".inf", ".sh", ".apk", ".chm", ".scf", ".xll", ".docm", ".xlsm", ".pptm"}


def is_runnable(item: Mapping[str, object]) -> bool:
    return extension_of(item) in RUNNABLE


def extension_of(item: Mapping[str, object]) -> str:
    name = item.get("original_name") or item.get("title") or ""
    return PurePath(str(name)).suffix.lower()


def kind_for(item: Mapping[str, object]) -> str:
    """Icon kind for a vault row (dict with kind / original_name / title)."""
    if item.get("kind") == "url":
        return "link"
    if item.get("kind") == "text":
        return "text"
    return _BY_EXTENSION.get(extension_of(item), "file")


def kind_for_path(name: str) -> str:
    return _BY_EXTENSION.get(PurePath(name).suffix.lower(), "file")


def preview_mode(item: Mapping[str, object]) -> str:
    """How the vault window should preview the item."""
    if item.get("kind") in ("text", "url"):
        return "text"
    ext = extension_of(item)
    if ext in ANIMATED_PREVIEW:
        return "animated_image"
    if ext in IMAGE_PREVIEW:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in TEXT_PREVIEW:
        return "text_file"
    return "icon_only"


def sniff(head: bytes) -> str | None:
    """Real content type from the first bytes (never trust the saved file name)."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"BM"):
        return "bmp"
    if head.startswith(b"%PDF-"):
        return "pdf"
    return None


def preview_for_content(mode: str, head: bytes) -> str:
    """Correct the name-based preview mode with what the bytes actually are."""
    found = sniff(head)
    if found == "pdf":
        return "pdf"
    if found in ("gif", "webp"):
        return "animated_image"
    if found in ("png", "jpeg", "bmp"):
        return "image"
    if mode in ("image", "animated_image", "pdf"):
        return "icon_only"  # named like an image/PDF but isn't one we decode
    return mode


_INVISIBLE = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
              0x200E, 0x200F, 0x061C}


def clean_text(text: str) -> str:
    """Drop control and direction-override characters that could disguise content."""
    return "".join(ch for ch in text
                   if ch in "\n\t" or (ord(ch) >= 32 and ord(ch) != 127
                                       and ord(ch) not in _INVISIBLE))


def decode_text(data: bytes) -> str | None:
    """Decode a text file's head (UTF-8 / UTF-16 with BOM); None if it looks binary."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return clean_text(data.decode("utf-16", errors="replace"))
        except UnicodeError:
            return None
    if b"\x00" in data[:4096]:
        return None
    return clean_text(data.decode("utf-8-sig", errors="replace"))


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
