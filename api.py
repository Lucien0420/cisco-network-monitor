"""
FastAPI backend for monitoring data API.
Reads from SQLite and data_cleaning to serve cleaned records and time-series data.
Uses OAuth2 password flow + JWT; protected routes require Bearer token.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

from database import TestDatabase

# Dynamic import wrapper to support /reload-parsers hot-reload
def _get_clean_fns():
    import data_cleaning
    return data_cleaning.load_and_clean_from_db, data_cleaning.to_time_series_rows

# Environment variables (do not hardcode secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PWD = os.environ.get("ADMIN_PWD", "admin")

# Must match main.py defaults
DB_DIR = os.environ.get("MONITOR_DB_DIR", "data")
DB_NAME = os.environ.get("MONITOR_DB_NAME", "dvt_monitor_results.db")
DEVICES_FILE = os.environ.get("MONITOR_DEVICES_FILE", "devices.json")

app = FastAPI(
    title="Switch Monitor API",
    description="Switch monitoring data API (OAuth2 + JWT). Raw records, cleaned data, and time-series.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


def _get_db():
    return TestDatabase(db_dir=DB_DIR, db_name=DB_NAME)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Dependency: verify Bearer token; 401 if missing or invalid."""
    if not credentials or credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to obtain token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------- Public: reload parsers (no auth, for hot-reload when API uses stale code) ----------
@app.get("/reload-parsers")
def reload_parsers():
    """Force reload data_cleaning module to pick up code changes without restart."""
    import importlib
    import data_cleaning
    importlib.reload(data_cleaning)
    return {
        "status": "ok",
        "message": "Parsers reloaded",
        "parsers": list(data_cleaning.PARSERS.keys()),
    }


# ---------- Public: health check (for load balancer, no auth) ----------
@app.get("/health")
def health():
    """Health check including parser status (confirms data_cleaning is loaded)."""
    from data_cleaning import PARSERS
    has_memory = "memory" in PARSERS
    has_interfaces_summary = "interfaces_summary" in PARSERS
    return {
        "status": "ok",
        "parsers_ok": has_memory and has_interfaces_summary,
        "parsers": list(PARSERS.keys()),
    }


# ---------- OAuth2: login for token ----------
@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Exchange credentials for JWT (OAuth2 password flow)."""
    if form_data.username != ADMIN_USER or form_data.password != ADMIN_PWD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}


# ---------- Protected: data API ----------
@app.get("/records")
def get_records(limit: int = Query(100, ge=1, le=5000), payload: dict = Depends(verify_token)):
    """Fetch latest N raw monitoring records (unparsed)."""
    db = _get_db()
    rows = db.fetch_latest_records(limit=limit)
    return {"count": len(rows), "records": rows}


@app.get("/cleaned")
def get_cleaned(limit: int = Query(500, ge=1, le=5000), payload: dict = Depends(verify_token)):
    """Fetch latest N cleaned records (with parsed fields)."""
    db = _get_db()
    load_and_clean_from_db, _ = _get_clean_fns()
    cleaned = load_and_clean_from_db(db, limit=limit)
    return {"count": len(cleaned), "records": cleaned}


@app.get("/time_series")
def get_time_series(
    limit: int = Query(500, ge=1, le=5000),
    metrics: Optional[str] = Query("cpu,memory,version,vlan,interfaces_summary", description="Comma-separated, e.g. cpu,memory,version,vlan,interfaces_summary"),
    payload: dict = Depends(verify_token),
):
    """Fetch time-series data for charts (CPU, memory, etc.)."""
    db = _get_db()
    load_and_clean_from_db, to_time_series_rows = _get_clean_fns()
    cleaned = load_and_clean_from_db(db, limit=limit)
    value_keys = [m.strip() for m in metrics.split(",") if m.strip()]
    rows = to_time_series_rows(cleaned, value_keys=value_keys or None)
    return {"count": len(rows), "rows": rows}


@app.get("/devices")
def get_devices(payload: dict = Depends(verify_token)):
    """Fetch configured device list (from devices.json)."""
    path = DEVICES_FILE
    if not os.path.isfile(path):
        return {"count": 0, "devices": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            devices = json.load(f)
    except Exception as e:
        return {"count": 0, "devices": [], "error": str(e)}
    out = []
    for d in devices:
        safe = {k: ("***" if k == "password" else v) for k, v in d.items()}
        out.append(safe)
    return {"count": len(out), "devices": out}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
