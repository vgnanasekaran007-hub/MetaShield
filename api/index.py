"""
Vercel WSGI Entry Point for MetaShield
=======================================
Vercel's @vercel/python builder looks for an 'app' (WSGI callable)
at the module level in api/index.py.

All HTTP requests are rewritten here via vercel.json rewrites.
"""

import sys
import os

# Add the project root to sys.path so we can import app.py and utils/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure writable /tmp directories exist before the app starts
os.makedirs("/tmp/metashield/uploads", exist_ok=True)
os.makedirs("/tmp/metashield/downloads", exist_ok=True)

# Import and expose the Flask WSGI app
from app import app, init_db  # noqa: E402

# Initialise the database in /tmp on cold start
try:
    init_db()
except Exception:
    pass
