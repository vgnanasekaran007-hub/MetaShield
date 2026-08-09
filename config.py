"""
MetaShield Configuration
========================
Central configuration for the MetaShield application.
"""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


# Detect if running in a serverless/read-only environment (e.g. Vercel, AWS Lambda, or read-only filesystem)
IS_SERVERLESS = os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or not os.access(BASE_DIR, os.W_OK)


class Config:
    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "metashield-secret-key-change-in-production")
    WTF_CSRF_ENABLED = True

    # ── Upload settings ───────────────────────────────────────────────────────
    if IS_SERVERLESS:
        UPLOAD_FOLDER = "/tmp/metashield/uploads"
        DOWNLOAD_FOLDER = "/tmp/metashield/downloads"
    else:
        UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
        DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "static", "downloads")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "tiff", "tif", "webp"}

    # ── Database ──────────────────────────────────────────────────────────────
    if IS_SERVERLESS:
        DATABASE = "/tmp/metashield/database.db"
    else:
        DATABASE = os.path.join(BASE_DIR, "database.db")

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_UPLOAD = "30 per hour"

    # ── App metadata ──────────────────────────────────────────────────────────
    APP_NAME = "MetaShield"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Image Metadata Analyzer & Editor"

    # ── Image processing ──────────────────────────────────────────────────────
    THUMBNAIL_SIZE = (300, 300)
    DEFAULT_QUALITY = 95
    COLOR_PALETTE_COLORS = 8

    # ── Auto-cleanup ──────────────────────────────────────────────────────────
    AUTO_DELETE_DAYS = 7          # delete uploads older than N days (0 = disabled)
