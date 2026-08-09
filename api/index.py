"""
Vercel WSGI Entry Point for MetaShield
=======================================
This file is the entry point for Vercel serverless deployment.
It imports the Flask app from the parent directory and exposes it
as 'app' for the @vercel/python builder.
"""

import sys
import os

# Add parent directory to path so Flask app can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: F401  (Vercel needs 'app' in scope)

# Ensure /tmp directories exist at cold start
os.makedirs("/tmp/metashield/uploads", exist_ok=True)
os.makedirs("/tmp/metashield/downloads", exist_ok=True)
