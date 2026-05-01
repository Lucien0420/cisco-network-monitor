"""
Central configuration — single source of truth for all environment variables.
Both main.py and api.py import from here; no os.environ.get() elsewhere.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Database ---
DB_DIR = os.environ.get("MONITOR_DB_DIR", "data")
DB_NAME = os.environ.get("MONITOR_DB_NAME", "dvt_monitor_results.db")
DEVICES_FILE = os.environ.get("MONITOR_DEVICES_FILE", "devices.json")

# --- API / Auth ---
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PWD = os.environ.get("ADMIN_PWD", "admin")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "60"))
