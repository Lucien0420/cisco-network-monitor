import sqlite3
import json
import os
from logger_config import setup_logger

# Database module logger
db_logger = setup_logger('database')

class TestDatabase:
    def __init__(self, db_dir='data', db_name='dvt_monitor_results.db'):
        """Initialize database and create tables."""
        
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, db_name)
        self._initialize_db()

    def _get_connection(self):
        """Create database connection."""
        try:
            return sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            db_logger.error(f"DB connection failed: {e}")
            raise

    def _initialize_db(self):
        """
        Create table matching monitor.py data structure.
        metrics column stores JSON (temperature, cpu, interfaces, etc.).
        """
        query = """
        CREATE TABLE IF NOT EXISTS monitor_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT NOT NULL,
            iteration INTEGER,
            metrics TEXT,
            timestamp TEXT,
            elapsed_time REAL,
            error_log TEXT,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        try:
            with self._get_connection() as conn:
                conn.execute(query)
                # Migration: add metrics column if missing
                try:
                    conn.execute("ALTER TABLE monitor_records ADD COLUMN metrics TEXT")
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise
                db_logger.info("Database initialized.")
        except sqlite3.Error as e:
            db_logger.error(f"DB init failed: {e}")
            raise

    def insert_monitor_data(self, data):
        """
        Insert data_point from monitor.py into database.
        data: dict matching monitor data_point; metrics: JSON of collected values.
        """
        metrics = data.get('metrics', data.get('temperature'))  # New format: metrics; legacy: temperature
        if isinstance(metrics, dict):
            metrics_str = json.dumps(metrics, ensure_ascii=False)
        else:
            metrics_str = json.dumps({'temperature': metrics}) if metrics is not None else '{}'
        query = """
        INSERT INTO monitor_records 
        (device, iteration, metrics, timestamp, elapsed_time, error_log)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            with self._get_connection() as conn:
                conn.execute(query, (
                    data.get('device'),
                    data.get('iteration'),
                    metrics_str,
                    data.get('timestamp'),
                    data.get('elapsed_time'),
                    data.get('error_log', None)
                ))
            db_logger.debug(f"[{data.get('device')}] Written to DB")
            return True
        except sqlite3.Error as e:
            db_logger.error(f"DB write failed: {e}", exc_info=True)
            return False

    def fetch_latest_records(self, limit=100):
        """Fetch latest records for Streamlit/API."""
        query = "SELECT * FROM monitor_records ORDER BY id DESC LIMIT ?"
        try:
            with self._get_connection() as conn:
                # row_factory for dict-like rows (Pandas-friendly)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            db_logger.error(f"Query failed: {e}")
            return []