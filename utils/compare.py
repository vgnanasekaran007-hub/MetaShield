"""
MetaShield – Metadata Comparator
==================================
Compare metadata of two images and produce a structured diff.
"""

from typing import Any, Dict, List, Tuple

from .metadata import extract_metadata


# ---------------------------------------------------------------------------

def compare_images(path_a: str, path_b: str) -> Dict:
    """
    Compare metadata of two images.

    Returns
    -------
    {
        "image_a": <metadata dict>,
        "image_b": <metadata dict>,
        "diff":    list of {key, value_a, value_b, status}
        "summary": {added, removed, changed, same, total}
    }
    """
    meta_a = extract_metadata(path_a)
    meta_b = extract_metadata(path_b)

    flat_a = _flatten(meta_a)
    flat_b = _flatten(meta_b)

    all_keys = sorted(set(flat_a) | set(flat_b))

    diff: List[Dict] = []
    counts = {"added": 0, "removed": 0, "changed": 0, "same": 0}

    for key in all_keys:
        va = flat_a.get(key, _MISSING)
        vb = flat_b.get(key, _MISSING)

        if va is _MISSING and vb is not _MISSING:
            status = "added"
        elif va is not _MISSING and vb is _MISSING:
            status = "removed"
        elif _val_str(va) != _val_str(vb):
            status = "changed"
        else:
            status = "same"

        counts[status] = counts.get(status, 0) + 1
        diff.append({
            "key": key,
            "value_a": _val_str(va) if va is not _MISSING else None,
            "value_b": _val_str(vb) if vb is not _MISSING else None,
            "status": status,
        })

    counts["total"] = len(all_keys)

    return {
        "image_a": meta_a,
        "image_b": meta_b,
        "diff": diff,
        "summary": counts,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MISSING = object()


def _flatten(meta: Dict, prefix: str = "", result: Dict = None) -> Dict:
    """Flatten nested metadata dict into dot-notation keys."""
    if result is None:
        result = {}
    for k, v in meta.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if k in ("histogram", "thumbnail", "color_palette"):
            continue  # skip binary / large data
        if isinstance(v, dict):
            _flatten(v, full_key, result)
        elif isinstance(v, list):
            result[full_key] = ", ".join(str(i) for i in v)
        else:
            result[full_key] = v
    return result


def _val_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()
