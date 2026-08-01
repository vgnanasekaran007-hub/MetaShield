"""
MetaShield – Metadata Editor
=============================
Edit writable EXIF/IPTC fields in images using piexif.
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import piexif
from PIL import Image


# ---------------------------------------------------------------------------
# Field registry  (piexif IFD → tag name → tag id)
# ---------------------------------------------------------------------------

EDITABLE_FIELDS: Dict[str, Dict] = {
    "Artist": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.Artist,
        "type": "str",
        "label": "Artist / Author",
    },
    "Copyright": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.Copyright,
        "type": "str",
        "label": "Copyright",
    },
    "ImageDescription": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.ImageDescription,
        "type": "str",
        "label": "Image Description",
    },
    "Software": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.Software,
        "type": "str",
        "label": "Software",
    },
    "Make": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.Make,
        "type": "str",
        "label": "Camera Make",
    },
    "Model": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.Model,
        "type": "str",
        "label": "Camera Model",
    },
    "DateTime": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.DateTime,
        "type": "datetime",
        "label": "Date/Time",
    },
    "DateTimeOriginal": {
        "ifd": "Exif",
        "tag": piexif.ExifIFD.DateTimeOriginal,
        "type": "datetime",
        "label": "Date Taken",
    },
    "UserComment": {
        "ifd": "Exif",
        "tag": piexif.ExifIFD.UserComment,
        "type": "str",
        "label": "User Comment",
    },
    "XPTitle": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.XPTitle,
        "type": "utf16",
        "label": "Title",
    },
    "XPAuthor": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.XPAuthor,
        "type": "utf16",
        "label": "Author (Windows)",
    },
    "XPKeywords": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.XPKeywords,
        "type": "utf16",
        "label": "Keywords",
    },
    "XPSubject": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.XPSubject,
        "type": "utf16",
        "label": "Subject",
    },
    "XPComment": {
        "ifd": "0th",
        "tag": piexif.ImageIFD.XPComment,
        "type": "utf16",
        "label": "Comment (Windows)",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_current_editable(filepath: str) -> Dict[str, Optional[str]]:
    """Return current values for all editable fields."""
    result = {k: None for k in EDITABLE_FIELDS}
    try:
        img = Image.open(filepath)
        exif_bytes = img.info.get("exif")
        img.close()
        if not exif_bytes:
            return result
        exif_data = piexif.load(exif_bytes)
        for field_name, meta in EDITABLE_FIELDS.items():
            ifd = exif_data.get(meta["ifd"], {})
            val = ifd.get(meta["tag"])
            if val is not None:
                result[field_name] = _decode(val, meta["type"])
    except Exception:
        pass
    return result


def edit_metadata(src_path: str, dst_path: str, edits: Dict[str, Any], quality: int = 95) -> Dict:
    """
    Apply *edits* dict to image and save to *dst_path*.

    Parameters
    ----------
    src_path  : source image path
    dst_path  : output path
    edits     : {field_name: new_value, ...} from EDITABLE_FIELDS keys
    quality   : JPEG output quality

    Returns
    -------
    dict with applied, skipped, dst_path
    """
    img = Image.open(src_path)
    original_format = (img.format or "JPEG").upper()
    if original_format == "JPG":
        original_format = "JPEG"
    img.load()

    # Load or initialise EXIF
    exif_bytes = img.info.get("exif", b"")
    try:
        exif_data = piexif.load(exif_bytes) if exif_bytes else _empty_exif()
    except Exception:
        exif_data = _empty_exif()

    applied: list = []
    skipped: list = []

    for field_name, new_val in edits.items():
        if field_name not in EDITABLE_FIELDS:
            skipped.append(f"{field_name} (unknown field)")
            continue
        meta = EDITABLE_FIELDS[field_name]
        try:
            encoded = _encode(str(new_val).strip(), meta["type"])
            if exif_data.get(meta["ifd"]) is None:
                exif_data[meta["ifd"]] = {}
            exif_data[meta["ifd"]][meta["tag"]] = encoded
            applied.append(field_name)
        except Exception as e:
            skipped.append(f"{field_name} ({e})")

    new_exif_bytes = piexif.dump(exif_data)

    save_kwargs: dict = {"format": original_format}
    if original_format == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
        save_kwargs["exif"] = new_exif_bytes
    elif original_format in ("TIFF", "TIF"):
        save_kwargs["format"] = "TIFF"
        save_kwargs["exif"] = new_exif_bytes

    out_img = img
    if original_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        out_img = img.convert("RGB")

    out_img.save(dst_path, **save_kwargs)
    img.close()

    return {
        "applied": applied,
        "skipped": skipped,
        "dst_path": dst_path,
    }


# ---------------------------------------------------------------------------
# Encode / Decode helpers
# ---------------------------------------------------------------------------

def _decode(val: Any, typ: str) -> Optional[str]:
    try:
        if isinstance(val, bytes):
            if typ == "utf16":
                return val.decode("utf-16-le", errors="replace").rstrip("\x00")
            if typ == "str":
                return val.decode("utf-8", errors="replace").rstrip("\x00")
            return val.decode("latin-1", errors="replace").rstrip("\x00")
        return str(val)
    except Exception:
        return None


def _encode(val: str, typ: str) -> bytes:
    if typ == "utf16":
        return val.encode("utf-16-le") + b"\x00\x00"
    if typ == "datetime":
        # normalise to EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
        try:
            dt = datetime.fromisoformat(val)
            val = dt.strftime("%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
        return val.encode("ascii") + b"\x00"
    return val.encode("utf-8") + b"\x00"


def _empty_exif() -> dict:
    return {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
