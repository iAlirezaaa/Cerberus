"""Build a reproducible ZIP of versioned Cerberus artwork.

Run from any directory:
    python scripts/package_animation_assets.py
    python scripts/package_animation_assets.py --output /path/to/assets.zip
No optional dependencies or network access required.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ANIMATIONS = ROOT / "assets" / "animations"
CONCEPTS = ROOT / "assets" / "concepts"
GOOD_SUFFIXES = {".png", ".gif", ".json", ".md"}
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024


def source_files() -> list[Path]:
    files: list[Path] = []
    for folder in (ANIMATIONS, CONCEPTS):
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing asset directory: {folder}")
        for file in folder.rglob("*"):
            if not file.is_file() or file.is_symlink():
                continue
            if file.suffix.lower() not in GOOD_SUFFIXES:
                continue
            if file.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f"Asset exceeds 32 MiB limit: {file}")
            files.append(file)
    for name in ("LICENSE", "NOTICE"):
        file = ROOT / name
        if file.exists():
            files.append(file)
    if not (ANIMATIONS / "cerberus_portal_enter.gif").exists():
        raise FileNotFoundError("Missing portal entrance GIF")
    if not (ANIMATIONS / "cerberus_bored_lookaround.gif").exists():
        raise FileNotFoundError("Missing bored look-around GIF")
    png_frames = [x for x in files if x.suffix.lower() == ".png" and "/frames/" in x.relative_to(ROOT).as_posix()]
    if len(png_frames) != 16:
        raise ValueError(f"Expected 16 animation PNG frames, got {len(png_frames)}")
    total = sum(file.stat().st_size for file in files)
    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"Total archive input exceeds {MAX_TOTAL_BYTES} bytes")
    return sorted(files, key=lambda f: f.relative_to(ROOT).as_posix())


def package(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = source_files()
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=7) as archive:
        for source in files:
            relative = source.relative_to(ROOT).as_posix()
            info = ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=7)
        if archive.testzip() is not None:
            raise IOError("ZIP CRC verification failed")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the Cerberus visual assets")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "Cerberus-visual-assets.zip")
    args = parser.parse_args()
    path = package(args.output.expanduser().resolve())
    print(f"Created {path} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
