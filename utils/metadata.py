"""
MetaShield – Metadata Extractor
================================
Extracts EXIF, XMP, IPTC, ICC profile and other metadata from images
using Pillow, piexif and exifread.
"""

import io
import os
import json
import math
import struct
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import piexif
import exifread
from PIL import Image, ExifTags, ImageStat

# ---------------------------------------------------------------------------
# Tag name helpers
# ---------------------------------------------------------------------------

def _tag_name(tag_id: int) -> str:
    """Return human-readable EXIF tag name for a given tag ID."""
    return ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")


def _gps_tag_name(tag_id: int) -> str:
    return ExifTags.GPSTAGS.get(tag_id, f"GPSTag_{tag_id}")


# ---------------------------------------------------------------------------
# GPS helpers
# ---------------------------------------------------------------------------

def _rational_to_float(value) -> Optional[float]:
    """Convert IFDRational or (num, den) tuple to float."""
    try:
        if hasattr(value, "numerator"):
            return float(value.numerator) / float(value.denominator) if value.denominator != 0 else 0.0
        if isinstance(value, tuple) and len(value) == 2:
            return float(value[0]) / float(value[1]) if value[1] != 0 else 0.0
        return float(value)
    except Exception:
        return None


def _parse_gps_coord(values, ref: str) -> Optional[float]:
    """Convert GPS (deg, min, sec) + ref to decimal degrees."""
    try:
        parts = [_rational_to_float(v) for v in values]
        if None in parts or len(parts) < 3:
            return None
        deg = parts[0] + parts[1] / 60.0 + parts[2] / 3600.0
        if ref in ("S", "W"):
            deg = -deg
        return round(deg, 7)
    except Exception:
        return None


def _extract_gps(gps_ifd: dict) -> Dict[str, Any]:
    """Parse raw GPSInfo IFD into a friendly dict."""
    gps: Dict[str, Any] = {}
    lat_val = lat_ref = lon_val = lon_ref = alt_val = None

    for tag_id, value in gps_ifd.items():
        name = _gps_tag_name(tag_id)
        if name == "GPSLatitude":
            lat_val = value
        elif name == "GPSLatitudeRef":
            lat_ref = str(value)
        elif name == "GPSLongitude":
            lon_val = value
        elif name == "GPSLongitudeRef":
            lon_ref = str(value)
        elif name == "GPSAltitude":
            alt_val = _rational_to_float(value)
        else:
            try:
                gps[name] = str(value)
            except Exception:
                gps[name] = repr(value)

    if lat_val and lat_ref:
        gps["Latitude"] = _parse_gps_coord(lat_val, lat_ref)
        gps["LatitudeRef"] = lat_ref
    if lon_val and lon_ref:
        gps["Longitude"] = _parse_gps_coord(lon_val, lon_ref)
        gps["LongitudeRef"] = lon_ref
    if alt_val is not None:
        gps["Altitude"] = round(alt_val, 2)

    if gps.get("Latitude") and gps.get("Longitude"):
        gps["MapsURL"] = (
            f"https://www.google.com/maps?q={gps['Latitude']},{gps['Longitude']}"
        )
        gps["HasGPS"] = True
    else:
        gps["HasGPS"] = False

    return gps


# ---------------------------------------------------------------------------
# Color palette extraction
# ---------------------------------------------------------------------------

def _extract_color_palette(img: Image.Image, n_colors: int = 8) -> List[str]:
    """Return top N dominant colors as hex strings."""
    try:
        small = img.convert("RGB").resize((150, 150))
        small = small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
        palette_data = small.getpalette()
        if not palette_data:
            return []
        colors = []
        for i in range(n_colors):
            r, g, b = palette_data[i * 3], palette_data[i * 3 + 1], palette_data[i * 3 + 2]
            colors.append(f"#{r:02x}{g:02x}{b:02x}")
        return colors
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Histogram data
# ---------------------------------------------------------------------------

def _extract_histogram(img: Image.Image) -> Dict[str, Any]:
    """Return per-channel histogram data suitable for Chart.js."""
    try:
        rgb = img.convert("RGB")
        hist = rgb.histogram()  # 256*3 values: R, G, B
        labels = list(range(256))
        return {
            "labels": labels,
            "red":   hist[0:256],
            "green": hist[256:512],
            "blue":  hist[512:768],
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

def extract_metadata(filepath: str) -> Dict[str, Any]:
    """
    Extract all available metadata from *filepath* and return a unified dict.

    Keys
    ----
    file_info      – size, name, extension …
    image_info     – width, height, mode, DPI …
    exif           – cleaned EXIF tag dict
    gps            – GPS info with lat/lon
    raw_exif       – raw tag values
    thumbnail      – base64 thumbnail if embedded
    color_palette  – list of dominant hex colors
    histogram      – RGB histogram for Chart.js
    icc_profile    – presence & description
    warnings       – list of non-fatal warnings
    """
    result: Dict[str, Any] = {
        "file_info": {},
        "image_info": {},
        "exif": {},
        "gps": {},
        "raw_exif": {},
        "thumbnail": None,
        "color_palette": [],
        "histogram": {},
        "icc_profile": {},
        "warnings": [],
    }

    # ── File info ─────────────────────────────────────────────────────────────
    stat = os.stat(filepath)
    fname = os.path.basename(filepath)
    ext = os.path.splitext(fname)[1].lstrip(".").upper()
    result["file_info"] = {
        "filename": fname,
        "extension": ext,
        "size_bytes": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
    }

    # ── Open image ────────────────────────────────────────────────────────────
    try:
        img = Image.open(filepath)
    except Exception as e:
        result["warnings"].append(f"Cannot open image: {e}")
        return result

    # ── Image info ────────────────────────────────────────────────────────────
    dpi = img.info.get("dpi", (72, 72))
    result["image_info"] = {
        "width": img.width,
        "height": img.height,
        "format": img.format or ext,
        "mode": img.mode,
        "megapixels": round(img.width * img.height / 1_000_000, 2),
        "aspect_ratio": _aspect_ratio(img.width, img.height),
        "dpi_x": round(dpi[0]) if isinstance(dpi, (list, tuple)) else 72,
        "dpi_y": round(dpi[1]) if isinstance(dpi, (list, tuple)) else 72,
        "has_transparency": img.mode in ("RGBA", "LA", "PA", "1") or "transparency" in img.info,
        "bit_depth": _bit_depth(img.mode),
        "animation_frames": getattr(img, "n_frames", 1),
    }

    # ── Color palette ─────────────────────────────────────────────────────────
    result["color_palette"] = _extract_color_palette(img)

    # ── Histogram ────────────────────────────────────────────────────────────
    result["histogram"] = _extract_histogram(img)

    # ── ICC Profile ───────────────────────────────────────────────────────────
    icc = img.info.get("icc_profile")
    if icc:
        result["icc_profile"] = {
            "present": True,
            "size_bytes": len(icc),
            "description": _parse_icc_description(icc),
        }
    else:
        result["icc_profile"] = {"present": False}

    # ── EXIF via Pillow ───────────────────────────────────────────────────────
    try:
        raw = img._getexif()  # type: ignore[attr-defined]
        if raw:
            exif_dict: Dict[str, Any] = {}
            for tag_id, value in raw.items():
                name = _tag_name(tag_id)
                if name == "GPSInfo":
                    result["gps"] = _extract_gps(value)
                elif name == "MakerNote":
                    exif_dict["MakerNote"] = f"<binary {len(value)} bytes>"
                else:
                    exif_dict[name] = _serialize(value)
            result["exif"] = exif_dict
    except Exception as e:
        result["warnings"].append(f"Pillow EXIF: {e}")

    # ── EXIF via exifread (richer tag set) ────────────────────────────────────
    try:
        with open(filepath, "rb") as fh:
            tags = exifread.process_file(fh, details=True)
        raw_exif: Dict[str, str] = {}
        for k, v in tags.items():
            if k.startswith("Thumbnail"):
                continue
            raw_exif[k] = str(v)
        result["raw_exif"] = raw_exif
    except Exception as e:
        result["warnings"].append(f"exifread: {e}")

    # ── Embedded thumbnail ────────────────────────────────────────────────────
    try:
        exif_bytes = img.info.get("exif")
        if exif_bytes:
            exif_data = piexif.load(exif_bytes)
            thumb = exif_data.get("thumbnail")
            if thumb:
                import base64
                result["thumbnail"] = "data:image/jpeg;base64," + base64.b64encode(thumb).decode()
    except Exception:
        pass

    # ── piexif structured EXIF ────────────────────────────────────────────────
    try:
        exif_bytes = img.info.get("exif")
        if exif_bytes:
            piexif_data = piexif.load(exif_bytes)
            structured = {}
            for ifd_name in ("0th", "Exif", "GPS", "1st"):
                ifd = piexif_data.get(ifd_name, {})
                for tag_id, val in ifd.items():
                    try:
                        tag_name = piexif.TAGS[ifd_name].get(tag_id, {}).get("name", f"Tag_{tag_id}")
                        structured[f"{ifd_name}.{tag_name}"] = _serialize(val)
                    except Exception:
                        pass
            result["piexif"] = structured
    except Exception:
        result["piexif"] = {}

    img.close()
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _aspect_ratio(w: int, h: int) -> str:
    g = math.gcd(w, h)
    return f"{w // g}:{h // g}"


def _bit_depth(mode: str) -> int:
    depths = {
        "1": 1, "L": 8, "P": 8, "RGB": 24,
        "RGBA": 32, "CMYK": 32, "YCbCr": 24,
        "LAB": 24, "HSV": 24, "I": 32, "F": 32,
        "LA": 16, "PA": 16, "RGBa": 32, "La": 16,
        "I;16": 16, "BGR;15": 15, "BGR;16": 16,
    }
    return depths.get(mode, 24)


def _serialize(value: Any) -> Any:
    """Make EXIF values JSON-serializable."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()
    if isinstance(value, tuple):
        # IFDRational or plain rational
        if len(value) == 2 and all(isinstance(v, int) for v in value):
            return f"{value[0]}/{value[1]}"
        return [_serialize(v) for v in value]
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        d = value.denominator
        n = value.numerator
        if d == 0:
            return 0
        f = n / d
        return round(f, 6) if f != int(f) else int(f)
    return value


def _parse_icc_description(icc_bytes: bytes) -> str:
    """Extract a human-readable name from raw ICC profile bytes."""
    try:
        # ICC profile description tag offset is typically at byte 128+
        desc = icc_bytes[128:256].decode("latin-1", errors="replace")
        desc = desc.replace("\x00", "").strip()
        return desc or "ICC Profile Present"
    except Exception:
        return "ICC Profile Present"
