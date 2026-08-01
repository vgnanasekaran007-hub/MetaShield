"""
MetaShield – Metadata Cleaner
==============================
Removes EXIF, GPS, XMP, IPTC, ICC profile, comments and thumbnail
from images. Supports selective or full removal.
"""

import io
import os
from typing import Dict, List, Optional

import piexif
from PIL import Image


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _save_clean(img: Image.Image, out_path: str, original_format: str, quality: int = 95):
    """Save *img* to *out_path* without any metadata."""
    fmt = (original_format or "JPEG").upper()
    if fmt in ("JPG",):
        fmt = "JPEG"
    save_kwargs: dict = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
    elif fmt == "WEBP":
        save_kwargs["quality"] = quality
        save_kwargs["method"] = 6
    img.save(out_path, **save_kwargs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

REMOVAL_OPTIONS = {
    "exif":        "EXIF metadata (camera, settings, dates)",
    "gps":         "GPS location data",
    "xmp":         "XMP/Adobe metadata",
    "iptc":        "IPTC press metadata",
    "comments":    "Image comments",
    "thumbnail":   "Embedded thumbnail",
    "icc_profile": "ICC color profile",
}


def remove_metadata(
    src_path: str,
    dst_path: str,
    options: Optional[List[str]] = None,
    quality: int = 95,
) -> Dict:
    """
    Remove metadata from *src_path* and save to *dst_path*.

    Parameters
    ----------
    src_path  : source image path
    dst_path  : destination image path
    options   : list of keys from REMOVAL_OPTIONS; None / empty = remove ALL
    quality   : JPEG/WebP output quality (1-100)

    Returns
    -------
    dict with keys: removed (list), size_before, size_after, savings_pct
    """
    remove_all = not options  # empty list or None → remove everything
    opts = set(options or list(REMOVAL_OPTIONS.keys()))

    size_before = os.path.getsize(src_path)
    img = Image.open(src_path)
    original_format = img.format or "JPEG"
    img.load()  # ensure full load

    removed: List[str] = []

    # ── Work on bytes via piexif for JPEG/TIFF ────────────────────────────────
    if original_format.upper() in ("JPEG", "JPG", "TIFF", "TIF"):
        try:
            exif_bytes = img.info.get("exif", b"")
            if exif_bytes:
                exif_data = piexif.load(exif_bytes)

                if "gps" in opts and exif_data.get("GPS"):
                    exif_data["GPS"] = {}
                    removed.append("GPS")

                if "thumbnail" in opts and exif_data.get("thumbnail"):
                    exif_data["thumbnail"] = None
                    exif_data["1st"] = {}
                    removed.append("Thumbnail")

                if "exif" in opts:
                    exif_data["Exif"] = {}
                    exif_data["0th"] = {}
                    removed.append("EXIF")

                if remove_all:
                    exif_bytes_new = b""
                else:
                    exif_bytes_new = piexif.dump(exif_data)
            else:
                exif_bytes_new = b""
        except Exception:
            exif_bytes_new = b""
            removed.append("EXIF (forced)")
    else:
        exif_bytes_new = b""

    # ── Strip image info dict ──────────────────────────────────────────────────
    clean_info = {}
    if "icc_profile" not in opts and not remove_all:
        icc = img.info.get("icc_profile")
        if icc:
            clean_info["icc_profile"] = icc
    else:
        if img.info.get("icc_profile"):
            removed.append("ICC Profile")

    if "comments" in opts or remove_all:
        if img.info.get("comment"):
            removed.append("Comments")
    else:
        if img.info.get("comment"):
            clean_info["comment"] = img.info["comment"]

    # ── Re-create image without metadata ─────────────────────────────────────
    buf = io.BytesIO()
    fmt = original_format.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    save_kwargs: dict = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
        if exif_bytes_new:
            save_kwargs["exif"] = exif_bytes_new
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
        if "icc_profile" in clean_info:
            save_kwargs["icc_profile"] = clean_info["icc_profile"]
    elif fmt == "WEBP":
        save_kwargs["quality"] = quality
        save_kwargs["method"] = 6
    elif fmt in ("TIFF", "TIF"):
        save_kwargs["format"] = "TIFF"
        if exif_bytes_new:
            save_kwargs["exif"] = exif_bytes_new

    # Convert RGBA → RGB for JPEG
    out_img = img
    if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        out_img = img.convert("RGB")

    out_img.save(dst_path, **save_kwargs)
    img.close()

    size_after = os.path.getsize(dst_path)
    savings = max(0.0, round((size_before - size_after) / size_before * 100, 1))

    if not removed:
        removed.append("Metadata (all)")

    return {
        "removed": removed,
        "size_before": size_before,
        "size_after": size_after,
        "size_before_human": _human(size_before),
        "size_after_human": _human(size_after),
        "savings_pct": savings,
        "dst_path": dst_path,
    }


def batch_remove(src_paths: List[str], dst_folder: str, options=None, quality: int = 95) -> List[Dict]:
    """Remove metadata from multiple images."""
    results = []
    os.makedirs(dst_folder, exist_ok=True)
    for src in src_paths:
        fname = os.path.basename(src)
        dst = os.path.join(dst_folder, "clean_" + fname)
        try:
            r = remove_metadata(src, dst, options, quality)
            r["filename"] = fname
            r["success"] = True
        except Exception as e:
            r = {"filename": fname, "success": False, "error": str(e)}
        results.append(r)
    return results


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n} GB"
