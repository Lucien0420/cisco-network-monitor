# monitor.py
from driver import ProfessionalSwitchDriver
from logger_config import setup_logger

monitor_logger = setup_logger('monitor')
import time
import json
import os
from datetime import datetime

def real_time_monitor_task(device_info, db=None):
    """
    Real-time monitoring task (compatible with TestScheduler).

    Args:
        device_info: Dict with ip/host, username, password, device_type,
            monitor_duration (seconds), monitor_max_iterations.
        db: Optional TestDatabase instance; if provided, each data_point is written immediately.

    Returns:
        Monitoring result dict.
    """
    # Extract monitoring parameters from device_info
    duration = device_info.get('monitor_duration')
    max_iterations = device_info.get('monitor_max_iterations')
    
    # Use IP:Port or device name as unique ID to distinguish same-IP different-port devices
    ip = device_info.get('ip') or device_info.get('host', 'unknown')
    port = device_info.get('port', '')
    device_name = device_info.get('name', '')
    
    # Prefer device_name, then IP:Port, then IP
    if device_name:
        device_id = device_name
    elif port:
        device_id = f"{ip}:{port}"
    else:
        device_id = ip
    
    # Warn if infinite monitoring (no duration or max_iterations)
    if not duration and not max_iterations:
        monitor_logger.warning(
            f"[{device_id}] Warning: infinite monitoring! Set monitor_duration or monitor_max_iterations."
        )
    
    # Collect commands: per-device config; default to temperature for backward compatibility
    _default_commands = [{'key': 'temperature', 'command': 'show system temperature'}]
    collect_commands = device_info.get('collect_commands', _default_commands)

    # Data file path: use data_dir from device_info or default 'data'
    data_dir = device_info.get('data_dir', 'data')
    os.makedirs(data_dir, exist_ok=True)
    data_file = os.path.join(data_dir, f'{device_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl')
    
    driver = ProfessionalSwitchDriver(device_info)
    if not driver.connect():
        monitor_logger.error(f"[{device_id}] Connection failed")
        return {
            'device': device_id,
            'status': 'failed',
            'error': 'Connection failed',
            'data_file': None
        }
    
    monitor_logger.info(f"[{device_id}] Starting monitor, data to: {data_file}")
    
    start_time = time.time()
    iteration = 0
    error_count = 0
    data_file_handle = open(data_file, 'w', encoding='utf-8')
    
    try:
        while True:
            # Check stop conditions
            if duration and (time.time() - start_time) >= duration:
                break
            
            if max_iterations and iteration >= max_iterations:
                break
            
            iteration += 1

            # 1. Active collection: run collect_commands per device
            metrics = {}
            for item in collect_commands:
                key = item.get('key', 'unknown')
                cmd = item.get('command', '')
                if not cmd:
                    continue
                result = driver.send_command(cmd)
                metrics[key] = result if result is not None else ''
                if result is None:
                    error_count += 1

            # 2. Passive: read switch logs via read_channel (optional)
            unexpected_logs = driver.read_channel()

            # Record data (metrics: temperature, cpu, interfaces, etc.)
            data_point = {
                'device': device_id,
                'iteration': iteration,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat(),
                'elapsed_time': time.time() - start_time
            }
            # unexpected_logs: optional
            if "ERROR" in unexpected_logs:
                monitor_logger.warning(f"[{device_id}] Unexpected alert: {unexpected_logs}")
                data_point['error_log'] = unexpected_logs
                error_count += 1
            
            # Write to file immediately (JSONL: one JSON per line, UTF-8)
            try:
                data_file_handle.write(json.dumps(data_point, ensure_ascii=False) + '\n')
                data_file_handle.flush()  # Flush to disk
            except Exception as e:
                monitor_logger.error(f"[{device_id}] Write to file failed: {e}", exc_info=True)

            # If db provided, write to database in real time
            if db is not None:
                try:
                    db.insert_monitor_data(data_point)
                except Exception as e:
                    monitor_logger.warning(f"[{device_id}] DB write failed (skipped): {e}")
            
            monitor_logger.info(f"[{device_id}] iter {iteration} - metrics: {list(metrics.keys())}")
            
            time.sleep(5)  # Throttle to reduce CPU load
           
    except KeyboardInterrupt:
        monitor_logger.warning(f"[{device_id}] Interrupt received, stopping")
    except Exception as e:
        monitor_logger.error(f"[{device_id}] Error during monitoring: {e}", exc_info=True)
        # Check data_file_handle exists before closing
        if 'data_file_handle' in locals():
            data_file_handle.close()
        driver.close()
        return {
            'device': device_id,
            'status': 'error',
            'error': str(e),
            'data_file': data_file
        }
    # finally: always runs
    finally:
        if 'data_file_handle' in locals():
            data_file_handle.close()
        driver.close()
        monitor_logger.info(f"[{device_id}] Monitor ended, data saved to: {data_file}")
    
    return {
        'device': device_id,
        'status': 'completed',
        'iterations': iteration,
        'error_count': error_count,
        'duration': time.time() - start_time,
        'data_file': data_file
    }