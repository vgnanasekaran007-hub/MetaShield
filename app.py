"""
MetaShield – Main Flask Application
=====================================
Image Metadata Analyzer, Editor & Cleaner

Run:
    python app.py

API Endpoints:
    POST   /upload              Upload one or more images
    GET    /metadata/<filename> Get full metadata for a file
    POST   /edit                Edit metadata fields
    POST   /remove              Strip metadata (selective / all)
    POST   /compare             Compare two images
    GET    /history             List history (JSON)
    GET    /download/<filename> Download a file
    POST   /delete/<int:id>     Delete a history record
    GET    /export/<fn>/<fmt>   Export metadata as json/csv/txt/pdf
    GET    /analytics           Chart data for history page
"""

import io
import json
import os
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Flask, abort, flash, jsonify, render_template,
    request, send_file, send_from_directory, url_for,
)
from werkzeug.utils import secure_filename

from config import Config
from utils.metadata import extract_metadata
from utils.cleaner import remove_metadata, batch_remove
from utils.editor import edit_metadata, get_current_editable, EDITABLE_FIELDS
from utils.compare import compare_images
from utils.export import export_json, export_csv, export_txt, export_pdf

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)

# Ensure required directories exist
for d in (app.config["UPLOAD_FOLDER"], app.config["DOWNLOAD_FOLDER"]):
    os.makedirs(d, exist_ok=True)


# ── Database ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory."""
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS uploads (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            original_name TEXT NOT NULL,
            operation     TEXT NOT NULL DEFAULT 'analyze',
            file_size     INTEGER,
            created_at    TEXT NOT NULL,
            metadata_json TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    conn.close()
    print("[MetaShield] Database initialised.")


# ── Utility helpers ───────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in app.config["ALLOWED_EXTENSIONS"]


def sanitise_filename(filename: str) -> str:
    """Remove path traversal characters, keep name safe."""
    name = secure_filename(filename)
    name = re.sub(r"[^a-zA-Z0-9._\-]", "_", name)
    return name or "upload"


def save_history(filename: str, original: str, operation: str,
                 size: int, metadata: dict) -> int:
    """Insert an upload record and return its id."""
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO uploads (filename, original_name, operation, file_size, created_at, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (filename, original, operation, size, datetime.utcnow().isoformat(), json.dumps(metadata, default=str)),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


def error_response(msg: str, code: int = 400) -> Tuple[Any, int]:
    return jsonify({"success": False, "error": msg}), code


# ── Rate limiter (simple in-memory, per-IP) ───────────────────────────────────

_rate_store: Dict[str, List[float]] = {}

def rate_limit(max_calls: int = 30, window: int = 3600):
    """Decorator for basic in-memory rate limiting."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            import time
            ip = request.remote_addr or "unknown"
            now = time.time()
            history = _rate_store.get(ip, [])
            history = [t for t in history if now - t < window]
            if len(history) >= max_calls:
                return error_response("Rate limit exceeded. Try again later.", 429)
            history.append(now)
            _rate_store[ip] = history
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", editable_fields=EDITABLE_FIELDS)


@app.route("/compare")
def compare_page():
    return render_template("compare.html")


@app.route("/history")
def history_page():
    return render_template("history.html")


# ── API: Upload ───────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
@rate_limit(max_calls=30, window=3600)
def upload():
    """
    Upload one or more image files.
    Returns list of {filename, original_name, record_id, metadata} objects.
    """
    if "file" not in request.files:
        return error_response("No file part in request.")

    files = request.files.getlist("file")
    if not files or all(f.filename == "" for f in files):
        return error_response("No files selected.")

    results = []
    for f in files:
        if f.filename == "":
            continue
        if not allowed_file(f.filename):
            results.append({
                "original_name": f.filename,
                "success": False,
                "error": f"Format not allowed. Supported: {', '.join(app.config['ALLOWED_EXTENSIONS'])}",
            })
            continue

        ext = f.filename.rsplit(".", 1)[-1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)

        try:
            f.save(save_path)
        except Exception as e:
            results.append({"original_name": f.filename, "success": False, "error": str(e)})
            continue

        # Check size after save
        size = os.path.getsize(save_path)
        if size > app.config["MAX_CONTENT_LENGTH"]:
            os.remove(save_path)
            results.append({
                "original_name": f.filename,
                "success": False,
                "error": "File exceeds 20 MB limit.",
            })
            continue

        metadata = extract_metadata(save_path)
        record_id = save_history(unique_name, f.filename, "analyze", size, metadata)

        results.append({
            "success": True,
            "filename": unique_name,
            "original_name": f.filename,
            "record_id": record_id,
            "metadata": metadata,
        })

    return jsonify({"success": True, "files": results})


# ── API: Metadata ─────────────────────────────────────────────────────────────

@app.route("/metadata/<path:filename>")
def get_metadata(filename: str):
    """Return full metadata for an uploaded file."""
    safe = sanitise_filename(filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe)
    if not os.path.isfile(filepath):
        return error_response("File not found.", 404)
    meta = extract_metadata(filepath)
    # Also return current editable values
    meta["editable"] = get_current_editable(filepath)
    return jsonify({"success": True, "metadata": meta})


# ── API: Edit ─────────────────────────────────────────────────────────────────

@app.route("/edit", methods=["POST"])
def edit():
    """
    Edit metadata fields.
    Body JSON: {filename, edits: {field: value, ...}}
    """
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    edits = data.get("edits", {})

    if not filename:
        return error_response("filename is required.")
    if not edits:
        return error_response("No edits provided.")

    safe = sanitise_filename(filename)
    src = os.path.join(app.config["UPLOAD_FOLDER"], safe)
    if not os.path.isfile(src):
        return error_response("File not found.", 404)

    # Save edited copy into downloads/
    base, ext = os.path.splitext(safe)
    dst_name = f"edited_{base}{ext}"
    dst = os.path.join(app.config["DOWNLOAD_FOLDER"], dst_name)

    try:
        result = edit_metadata(src, dst, edits)
        size = os.path.getsize(dst)
        # Also update the source in-place so subsequent metadata reads are fresh
        import shutil
        shutil.copy2(dst, src)
        save_history(dst_name, f"edited_{filename}", "edit", size, {})
        return jsonify({"success": True, "download_name": dst_name, **result})
    except Exception as e:
        return error_response(str(e))


# ── API: Remove ───────────────────────────────────────────────────────────────

@app.route("/remove", methods=["POST"])
def remove():
    """
    Remove metadata.
    Body JSON: {filename, options: ["exif","gps",...], quality: 95}
    options=[] or omitted → remove ALL.
    """
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    options = data.get("options", [])   # empty = remove all
    quality = int(data.get("quality", 95))

    if not filename:
        return error_response("filename is required.")

    safe = sanitise_filename(filename)
    src = os.path.join(app.config["UPLOAD_FOLDER"], safe)
    if not os.path.isfile(src):
        return error_response("File not found.", 404)

    base, ext = os.path.splitext(safe)
    dst_name = f"clean_{base}{ext}"
    dst = os.path.join(app.config["DOWNLOAD_FOLDER"], dst_name)

    try:
        result = remove_metadata(src, dst, options or None, quality)
        size = result["size_after"]
        save_history(dst_name, f"clean_{filename}", "remove", size, {})
        result["download_name"] = dst_name
        return jsonify({"success": True, **result})
    except Exception as e:
        return error_response(str(e))


# ── API: Batch remove ─────────────────────────────────────────────────────────

@app.route("/batch_remove", methods=["POST"])
def batch_remove_api():
    """
    Remove metadata from multiple uploaded files.
    Body JSON: {filenames: [...], options: [...], quality: 95}
    Returns a downloadable ZIP.
    """
    data = request.get_json(silent=True) or {}
    filenames = data.get("filenames", [])
    options = data.get("options", [])
    quality = int(data.get("quality", 95))

    if not filenames:
        return error_response("No filenames provided.")

    src_paths = []
    for fn in filenames:
        safe = sanitise_filename(fn)
        p = os.path.join(app.config["UPLOAD_FOLDER"], safe)
        if os.path.isfile(p):
            src_paths.append(p)

    if not src_paths:
        return error_response("No valid files found.")

    batch_dir = os.path.join(app.config["DOWNLOAD_FOLDER"], "batch")
    os.makedirs(batch_dir, exist_ok=True)

    results = batch_remove(src_paths, batch_dir, options or None, quality)

    # Build ZIP
    zip_name = f"metashield_clean_{uuid.uuid4().hex[:8]}.zip"
    zip_path = os.path.join(app.config["DOWNLOAD_FOLDER"], zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            if r.get("success") and os.path.isfile(r.get("dst_path", "")):
                zf.write(r["dst_path"], arcname=os.path.basename(r["dst_path"]))

    return jsonify({
        "success": True,
        "results": results,
        "zip_name": zip_name,
    })


# ── API: Compare ──────────────────────────────────────────────────────────────

@app.route("/compare_meta", methods=["POST"])
def compare_meta():
    """
    Compare metadata of two uploaded images.
    Body JSON: {filename_a, filename_b}
    """
    data = request.get_json(silent=True) or {}
    fn_a = sanitise_filename(data.get("filename_a", ""))
    fn_b = sanitise_filename(data.get("filename_b", ""))

    if not fn_a or not fn_b:
        return error_response("Both filename_a and filename_b are required.")

    path_a = os.path.join(app.config["UPLOAD_FOLDER"], fn_a)
    path_b = os.path.join(app.config["UPLOAD_FOLDER"], fn_b)

    for p in (path_a, path_b):
        if not os.path.isfile(p):
            return error_response(f"File not found: {os.path.basename(p)}", 404)

    try:
        result = compare_images(path_a, path_b)
        return jsonify({"success": True, **result})
    except Exception as e:
        return error_response(str(e))


# ── API: History ──────────────────────────────────────────────────────────────

@app.route("/api/history")
def api_history():
    """Return paginated upload history as JSON."""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    search = request.args.get("q", "").strip()
    offset = (page - 1) * per_page

    conn = get_db()
    if search:
        rows = conn.execute(
            """SELECT id, filename, original_name, operation, file_size, created_at
               FROM uploads
               WHERE original_name LIKE ?
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (f"%{search}%", per_page, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM uploads WHERE original_name LIKE ?",
            (f"%{search}%",)
        ).fetchone()[0]
    else:
        rows = conn.execute(
            """SELECT id, filename, original_name, operation, file_size, created_at
               FROM uploads ORDER BY id DESC LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    conn.close()

    return jsonify({
        "success": True,
        "records": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
    })


# ── API: Download ─────────────────────────────────────────────────────────────

@app.route("/download/<path:filename>")
def download(filename: str):
    """Download a file from uploads or downloads folder."""
    safe = sanitise_filename(filename)
    # Check downloads first, then uploads
    for folder in (app.config["DOWNLOAD_FOLDER"], app.config["UPLOAD_FOLDER"]):
        filepath = os.path.join(folder, safe)
        if os.path.isfile(filepath):
            return send_from_directory(folder, safe, as_attachment=True)
    abort(404)


@app.route("/download_zip/<path:filename>")
def download_zip(filename: str):
    safe = sanitise_filename(filename)
    filepath = os.path.join(app.config["DOWNLOAD_FOLDER"], safe)
    if not os.path.isfile(filepath):
        abort(404)
    return send_from_directory(app.config["DOWNLOAD_FOLDER"], safe, as_attachment=True)


# ── API: Delete ───────────────────────────────────────────────────────────────

@app.route("/delete/<int:record_id>", methods=["POST", "DELETE"])
def delete_record(record_id: int):
    """Delete a history record (and its files if they exist)."""
    conn = get_db()
    row = conn.execute("SELECT * FROM uploads WHERE id=?", (record_id,)).fetchone()
    if not row:
        conn.close()
        return error_response("Record not found.", 404)

    # Remove files
    for folder in (app.config["UPLOAD_FOLDER"], app.config["DOWNLOAD_FOLDER"]):
        p = os.path.join(folder, row["filename"])
        if os.path.isfile(p):
            try:
                os.remove(p)
            except Exception:
                pass

    conn.execute("DELETE FROM uploads WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "id": record_id})


# ── API: Export metadata ───────────────────────────────────────────────────────

@app.route("/export/<path:filename>/<fmt>")
def export_meta(filename: str, fmt: str):
    """Export metadata as json / csv / txt / pdf."""
    safe = sanitise_filename(filename)
    src = os.path.join(app.config["UPLOAD_FOLDER"], safe)
    if not os.path.isfile(src):
        return error_response("File not found.", 404)

    meta = extract_metadata(src)
    base = os.path.splitext(safe)[0]
    fmt = fmt.lower()

    if fmt not in ("json", "csv", "txt", "pdf"):
        return error_response("Unsupported format. Use json, csv, txt or pdf.", 400)

    dst_name = f"metadata_{base}.{fmt}"
    dst = os.path.join(app.config["DOWNLOAD_FOLDER"], dst_name)

    fn_map = {"json": export_json, "csv": export_csv, "txt": export_txt, "pdf": export_pdf}
    try:
        fn_map[fmt](meta, dst)
    except Exception as e:
        return error_response(f"Export failed: {e}")

    mime_map = {
        "json": "application/json",
        "csv": "text/csv",
        "txt": "text/plain",
        "pdf": "application/pdf",
    }
    return send_from_directory(
        app.config["DOWNLOAD_FOLDER"],
        dst_name,
        as_attachment=True,
        mimetype=mime_map[fmt],
    )


# ── API: Analytics ────────────────────────────────────────────────────────────

@app.route("/analytics")
def analytics():
    """Return chart data for the history/analytics page."""
    conn = get_db()

    # Operations breakdown
    ops = conn.execute(
        "SELECT operation, COUNT(*) as cnt FROM uploads GROUP BY operation"
    ).fetchall()

    # Daily uploads (last 14 days)
    daily = conn.execute(
        """SELECT DATE(created_at) as day, COUNT(*) as cnt
           FROM uploads
           WHERE DATE(created_at) >= DATE('now', '-14 days')
           GROUP BY day ORDER BY day"""
    ).fetchall()

    # Formats
    formats_raw = conn.execute(
        "SELECT original_name FROM uploads ORDER BY id DESC LIMIT 200"
    ).fetchall()

    format_counts: Dict[str, int] = {}
    for row in formats_raw:
        ext = row["original_name"].rsplit(".", 1)[-1].upper() if "." in row["original_name"] else "UNK"
        format_counts[ext] = format_counts.get(ext, 0) + 1

    # Total stats
    totals = conn.execute(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(file_size),0) as total_size FROM uploads"
    ).fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "operations": {r["operation"]: r["cnt"] for r in ops},
        "daily": [{"day": r["day"], "count": r["cnt"]} for r in daily],
        "formats": format_counts,
        "totals": {"count": totals["cnt"], "size": totals["total_size"]},
    })


# ── API: Image preview (serve uploads) ───────────────────────────────────────

@app.route("/preview/<path:filename>")
def preview(filename: str):
    safe = sanitise_filename(filename)
    return send_from_directory(app.config["UPLOAD_FOLDER"], safe)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    if request.is_json or request.path.startswith(("/upload", "/metadata", "/api")):
        return jsonify({"success": False, "error": "Not found."}), 404
    return render_template("index.html"), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "File too large. Maximum is 20 MB."}), 413


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"success": False, "error": "Too many requests."}), 429


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("=" * 55)
    print("  MetaShield – Image Metadata Analyzer & Editor")
    print("  Running on http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, host="0.0.0.0", port=5000)
