"""Generate macOS and Windows app icons from the canonical MIRA PNG."""

import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "assets" / "MIRA-LOGO_v1.png"
ICNS_PATH = ROOT / "assets" / "AppIcon.icns"
ICO_PATH = ROOT / "assets" / "AppIcon.ico"

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]
ICONSET_FILES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}

# Modern ICNS chunk identifiers for each iconset representation.  These PNG
# chunks provide the same 16–1024 px coverage as the iconset passed to
# iconutil and are used only when the local iconutil cannot package a valid
# iconset (a failure observed with some Command Line Tools installations).
ICNS_CHUNKS = {
    "icon_16x16.png": b"icp4",
    "icon_16x16@2x.png": b"ic11",
    "icon_32x32.png": b"icp5",
    "icon_32x32@2x.png": b"ic12",
    "icon_128x128.png": b"ic07",
    "icon_128x128@2x.png": b"ic13",
    "icon_256x256.png": b"ic08",
    "icon_256x256@2x.png": b"ic14",
    "icon_512x512.png": b"ic09",
    "icon_512x512@2x.png": b"ic10",
}


def _square_icon(source, size: int):
    """Fit the complete source image on a transparent square without cropping."""
    from PIL import Image

    image = source.copy()
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - image.width) // 2, (size - image.height) // 2)
    canvas.alpha_composite(image, offset)
    return canvas


def _generate_ico(source) -> None:
    """Write the Windows multi-resolution icon directly from the PNG."""
    largest = _square_icon(source, 256)
    largest.save(ICO_PATH, format="ICO", sizes=ICO_SIZES)
    print(f"Saved: {ICO_PATH}")


def _write_icns_chunks(iconset: Path) -> None:
    """Package PNG iconset entries directly as a portable ICNS fallback."""
    chunks = []
    for filename, chunk_type in ICNS_CHUNKS.items():
        png_data = (iconset / filename).read_bytes()
        chunks.append(chunk_type + struct.pack(">I", len(png_data) + 8) + png_data)

    body = b"".join(chunks)
    ICNS_PATH.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def _generate_icns(source) -> None:
    """Build a complete iconset and let macOS iconutil package it."""
    iconutil = shutil.which("iconutil")
    if sys.platform != "darwin" or iconutil is None:
        print("Skipped AppIcon.icns: iconutil is available only on macOS.")
        return

    with tempfile.TemporaryDirectory(prefix="mira-icon-") as temp_dir:
        iconset = Path(temp_dir) / "AppIcon.iconset"
        iconset.mkdir()
        for filename, size in ICONSET_FILES.items():
            _square_icon(source, size).save(iconset / filename, format="PNG")

        try:
            subprocess.run(
                [iconutil, "-c", "icns", str(iconset), "-o", str(ICNS_PATH)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            # Some macOS/Command Line Tools combinations reject even an
            # iconset extracted by iconutil itself.  Keep generation reliable
            # by writing the documented PNG-backed ICNS chunks directly.
            detail = (error.stderr or error.stdout or "unknown iconutil error").strip()
            print(f"Warning: iconutil could not package the iconset: {detail}")
            print("Using the portable ICNS chunk fallback.")
            _write_icns_chunks(iconset)
    print(f"Saved: {ICNS_PATH}")


def convert() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow is not installed. Run: pip install Pillow")
        sys.exit(1)

    if not SOURCE_PATH.exists():
        print(f"Error: {SOURCE_PATH} not found.")
        sys.exit(1)

    try:
        with Image.open(SOURCE_PATH) as image:
            source = image.convert("RGBA")
            _generate_ico(source)
            _generate_icns(source)
    except Exception as e:
        print(f"Failed to generate app icons: {e}")
        sys.exit(1)


if __name__ == "__main__":
    convert()
