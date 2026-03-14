"""
Multi-device monitoring entry point.
Loads devices from devices.json, runs concurrent monitoring tasks, and writes to SQLite in real time.
"""
import json
import logging
from logger_config import setup_logger
from TestScheduler import TestScheduler
from monitor import real_time_monitor_task
from database import TestDatabase

main_logger = setup_logger('main', log_level=logging.INFO)

# Database directory (can share with JSONL output when devices use data_dir)
DB_DIR = 'data'
DB_NAME = 'dvt_monitor_results.db'

if __name__ == "__main__":
    devices_file = "devices.json"
    devices = []

    try:
        with open(devices_file, "r", encoding="utf-8") as f:
            devices = json.load(f)
        main_logger.info(f"Loaded {len(devices)} devices from {devices_file}")
    except FileNotFoundError:
        main_logger.error(f"Config file {devices_file} not found.")
        exit(1)
    except json.JSONDecodeError as e:
        main_logger.error(f"Failed to parse {devices_file}: {e}")
        exit(1)
    except Exception as e:
        main_logger.error(f"Error loading devices: {e}", exc_info=True)
        exit(1)

    if not devices:
        main_logger.warning("No devices in config. Tasks will not run.")
        exit(0)

    # Shared database instance for real-time writes from monitor loop
    try:
        db = TestDatabase(db_dir=DB_DIR, db_name=DB_NAME)
    except Exception as e:
        main_logger.error(f"Database init failed: {e}", exc_info=True)
        exit(1)

    main_logger.info("Starting multi-device monitoring (real-time DB write)...")

    # Pass db to real_time_monitor_task so each data_point is written immediately
    task_func = lambda dev: real_time_monitor_task(dev, db=db)

    with TestScheduler(max_workers=3) as scheduler:
        report = scheduler.run_tasks(
            task_func=task_func,
            target_list=devices,
            timeout=60,
            show_progress=True,
        )

    main_logger.info("Multi-device monitoring complete.")

    # Print summary report
    print("\n" + "=" * 50)
    print("Summary (success/fail/stats):")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("=" * 50)

    # Fetch latest records from database for verification
    try:
        latest = db.fetch_latest_records(limit=5)
        print(f"\nLatest {len(latest)} records from DB:")
        for r in latest:
            metrics_preview = r.get('metrics', '{}')
            if isinstance(metrics_preview, str):
                try:
                    m = json.loads(metrics_preview)
                    metrics_preview = list(m.keys()) if m else []
                except Exception:
                    metrics_preview = metrics_preview[:50]
            print(f"  id={r.get('id')} device={r.get('device')} iter={r.get('iteration')} metrics={metrics_preview}")
    except Exception as e:
        main_logger.warning(f"Failed to fetch latest records: {e}")

    main_logger.info("Done.")
