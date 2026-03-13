"""Download product images and save them locally."""

import hashlib
import os
from pathlib import Path

import requests
from PIL import Image

_OUTPUT_DIR = Path("output/images")
_TIMEOUT = 10  # seconds
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_MAX_SIZE = (600, 600)  # resize large images to save space


def download_image(url: str, product_number: int):
    """Download image from URL, save to output/images/, return relative path or None."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Determine extension from URL or default to jpg
    ext = _guess_extension(url)
    filename = f"product_{product_number:03d}{ext}"
    dest = _OUTPUT_DIR / filename

    # Return cached version if already downloaded
    if dest.exists():
        return str(dest)

    try:
        response = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS, stream=True)
        response.raise_for_status()

        # Write raw bytes first
        raw_path = dest.with_suffix(".raw")
        with open(raw_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Open with Pillow to validate and resize
        img = Image.open(raw_path).convert("RGB")
        img.thumbnail(_MAX_SIZE, Image.LANCZOS)
        img.save(dest, format="JPEG", quality=85)
        raw_path.unlink(missing_ok=True)

        return str(dest)

    except Exception as exc:
        print(f"  [download] Failed for product {product_number}: {exc}")
        # Clean up partial files
        for p in [dest, dest.with_suffix(".raw")]:
            if p.exists():
                p.unlink()
        return None


def _guess_extension(url: str) -> str:
    url_lower = url.lower().split("?")[0]
    for ext in (".png", ".webp", ".gif", ".jpeg", ".jpg"):
        if url_lower.endswith(ext):
            return ".jpg"  # always save as jpg
    return ".jpg"
