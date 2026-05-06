"""
Data cleaning module: reads monitor_records from DB/JSONL, parses metrics JSON,
and produces structured data for Streamlit or reports.

Design: monitor.py collect_commands can define any keys (temperature, cpu, interfaces, etc.).
This module parses registered keys via PARSERS into numbers/lists; unregistered keys are kept as-is.
To add a new metric (e.g. memory chart), add parse_xxx and register in PARSERS.
"""
import re
import json
from typing import List, Dict, Any, Optional, Callable
from logger_config import setup_logger

clean_logger = setup_logger('data_cleaning')

# ---------------------------------------------------------------------------
# Parsers: raw CLI string -> structured data (numbers, lists, or raw text)
# Extensible per vendor; default rules target Catalyst 9000
# ---------------------------------------------------------------------------

def parse_temperature(raw: str) -> Optional[float]:
    """Extract temperature (Celsius) from CLI output. Formats: '45 C', 'Temperature: 45', etc."""
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()
    
    # Skip "not found" error messages
    if "not found" in raw.lower():
        return 0.0

    # Match "number + optional C" or "Temperature: number" (case-insensitive)
    m = re.search(r'(?:temperature|temp)?\s*[:\s]*(\d+(?:\.\d+)?)\s*[cC]?\b', raw, re.IGNORECASE)
    if m:
        return float(m.group(1))
    
    # Fallback: any number
    m = re.search(r'\b(\d+(?:\.\d+)?)\s*', raw)
    return float(m.group(1)) if m else 0.0


def parse_cpu(raw: str) -> Optional[float]:
    """Extract CPU utilization (%) from CLI output. Formats: '5%', 'CPU utilization: 5%', etc."""
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()

    # Skip "not found" error messages
    if "not found" in raw.lower():
        return 0.0

    # Look for "5-second CPU: X.X %"
    m = re.search(r'5-second CPU:\s*(\d+(?:\.\d+)?)\s*%', raw, re.IGNORECASE)
    if m:
        return float(m.group(1))

    m = re.search(r'(?:cpu|utilization|usage)?\s*[:\s]*(\d+(?:\.\d+)?)\s*%?', raw, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r'\b(\d+(?:\.\d+)?)\s*%', raw)
    return float(m.group(1)) if m else 0.0


def parse_interfaces(raw: str) -> List[Dict[str, str]]:
    """Extract table data from interface CLI. Catalyst 9000: Port, Name, Status, Vlan, Duplex, Speed, Type."""
    if not raw or not str(raw).strip():
        return []
    lines = [ln.strip() for ln in str(raw).strip().splitlines() if ln.strip()]
    if not lines:
        return []
    header_like = re.search(r'port|interface|status', lines[0], re.IGNORECASE)
    rows = []
    for line in lines[1:] if header_like and len(lines) > 1 else lines:
        parts = re.split(r'\s{2,}|\t', line)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 1:
            row = {
                'port': parts[0],
                'name': parts[1] if len(parts) > 1 else '',
                'status': parts[2] if len(parts) > 2 else '',
                'vlan': parts[3] if len(parts) > 3 else '',
            }
            if len(parts) > 4:
                row['duplex'] = parts[4]
            if len(parts) > 5:
                row['speed'] = parts[5]
            rows.append(row)
    return rows if rows else []


def parse_version(raw: str) -> Optional[float]:
    """Extract uptime (days) from 'show version'. Format: 'uptime is 45 days, 3 hours, 22 minutes'."""
    if not raw or not str(raw).strip():
        return None
    
    # Extract uptime: look for "X days" or similar
    m = re.search(r'(\d+)\s+days?', raw, re.IGNORECASE)
    if m:
        return float(m.group(1))  # Return days as float
    
    return None


def parse_memory(raw: str) -> Optional[float]:
    """Extract memory usage (%) from 'show memory statistics'. Catalyst 9000: Processor line with Total(b), Used(b)."""
    if not raw or not str(raw).strip():
        return None
    
    for line in str(raw).strip().splitlines():
        if 'Processor' in line or 'processor' in line.lower():
            # Extract numbers. We expect: Head, Total, Used, Free, ...
            # We skip the first number (Head) and take the next two (Total, Used)
            nums = re.findall(r'\b(\d{5,})\b', line)
            if len(nums) >= 3:
                try:
                    total = int(nums[1])  # Total(b)
                    used = int(nums[2])   # Used(b)
                    if total > 0:
                        return round(used / total * 100.0, 2)
                except (ValueError, IndexError):
                    pass
    return None


def parse_vlan(raw: str) -> Optional[float]:
    """Count VLANs from 'show vlan brief' output."""
    lst = parse_vlan_list(raw)
    return float(len(lst)) if lst else None


def parse_vlan_list(raw: str) -> List[Dict[str, str]]:
    """Extract VLAN list from 'show vlan brief'. Format: VLAN Name Status Ports."""
    if not raw or not str(raw).strip():
        return []
    lines = str(raw).strip().splitlines()
    rows = []
    for line in lines:
        # Skip header and separator lines
        if re.match(r'^VLAN\s+Name', line, re.IGNORECASE) or re.match(r'^-+', line):
            continue
        parts = re.split(r'\s{2,}|\t', line)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 3:
            rows.append({
                'vlan_id': parts[0],
                'name': parts[1],
                'status': parts[2],
                'ports': parts[3] if len(parts) > 3 else '',
            })
    return rows


def parse_interfaces_summary(raw: str) -> Optional[float]:
    """Count up interfaces from 'show interfaces summary'. Catalyst: * marks up; exclude legend '*: interface is up'."""
    if not raw or not str(raw).strip():
        return None
    
    lines = str(raw).strip().splitlines()
    interfaces_up = 0
    
    for line in lines:
        line = line.strip()
        # Exclude legend line "*: interface is up"
        if line.startswith('*') and 'interface is up' not in line:
            interfaces_up += 1
    
    return float(interfaces_up) if interfaces_up > 0 else 0.0


def parse_inventory(raw: str) -> List[Dict[str, str]]:
    """Extract inventory info from 'show inventory'."""
    if not raw or not str(raw).strip():
        return []
    
    results = []
    # Match NAME: "...", DESCR: "..." and PID: ..., VID: ..., SN: ...
    # This is a simple parser for the common Cisco format
    name_descr_blocks = re.findall(r'NAME:\s*"([^"]*)",\s*DESCR:\s*"([^"]*)"', raw)
    pid_vid_sn_blocks = re.findall(r'PID:\s*([^,]*),\s*VID:\s*([^,]*),\s*SN:\s*(\S+)', raw)
    
    for i in range(min(len(name_descr_blocks), len(pid_vid_sn_blocks))):
        results.append({
            'name': name_descr_blocks[i][0].strip(),
            'descr': name_descr_blocks[i][1].strip(),
            'pid': pid_vid_sn_blocks[i][0].strip(),
            'vid': pid_vid_sn_blocks[i][1].strip(),
            'sn': pid_vid_sn_blocks[i][2].strip(),
        })
    return results


# Parser registry: metrics key -> parse function (extensible)
PARSERS: Dict[str, Callable[[str], Any]] = {
    'temperature': parse_temperature,
    'cpu': parse_cpu,
    'memory': parse_memory,
    'interfaces': parse_interfaces,
    'version': parse_version,
    'vlan': parse_vlan,
    'interfaces_summary': parse_interfaces_summary,
    'inventory': parse_inventory,
}


def parse_metric_value(key: str, raw_value: Any) -> Any:
    """Select parser by key, return structured result; unknown key returns raw text or None."""
    if raw_value is None:
        return None
    text = raw_value if isinstance(raw_value, str) else str(raw_value)
    parser = PARSERS.get(key.lower())
    if parser:
        try:
            return parser(text)
        except Exception as e:
            clean_logger.debug(f"Parse metrics[{key}] failed: {e}, keeping raw")
            return text
    return text if text.strip() else None


# ---------------------------------------------------------------------------
# Clean flow: single record -> add parsed fields
# ---------------------------------------------------------------------------

def clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse metrics JSON from single record, add parsed fields.
    record must have 'metrics' (JSON str or dict). Returns new dict with parsed: {key: value}.
    """
    out = dict(record)
    metrics_raw = record.get('metrics')
    if metrics_raw is None:
        out['parsed'] = {}
        return out
    if isinstance(metrics_raw, str):
        try:
            metrics_dict = json.loads(metrics_raw)
        except json.JSONDecodeError as e:
            clean_logger.warning(f"metrics invalid JSON: {e}")
            out['parsed'] = {}
            return out
    else:
        metrics_dict = metrics_raw if isinstance(metrics_raw, dict) else {}
    parsed = {}
    for key, value in metrics_dict.items():
        parsed[key] = parse_metric_value(key, value)
        # Also produce vlan_list for table display when vlan key exists
        if key == 'vlan' and value:
            parsed['vlan_list'] = parse_vlan_list(value if isinstance(value, str) else str(value))
    out['parsed'] = parsed
    return out


def clean_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Batch clean multiple records."""
    return [clean_record(r) for r in records]


# ---------------------------------------------------------------------------
# For Streamlit/reports: produce DataFrame-friendly structure from cleaned records
# ---------------------------------------------------------------------------

def to_time_series_rows(
    cleaned_records: List[Dict[str, Any]],
    value_keys: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Flatten cleaned records to time-series rows (one per metric value) for charts.
    value_keys: parsed keys for time-series; default cpu, memory, version, vlan, interfaces_summary.
    """
    if value_keys is None:
        value_keys = ['cpu', 'memory', 'version', 'vlan', 'interfaces_summary']
    rows = []
    for r in cleaned_records:
        base = {
            'id': r.get('id'),
            'device': r.get('device'),
            'iteration': r.get('iteration'),
            'timestamp': r.get('timestamp'),
            'recorded_at': r.get('recorded_at'),
            'elapsed_time': r.get('elapsed_time'),
        }
        parsed = r.get('parsed') or {}
        for k in value_keys:
            v = parsed.get(k)
            if v is not None and isinstance(v, (int, float)):
                rows.append({**base, 'metric': k, 'value': v})
        # Skip or store non-numeric values per key
    return rows


def get_device_metric_series(
    cleaned_records: List[Dict[str, Any]],
    device: str,
    metric: str,
) -> List[Dict[str, Any]]:
    """Time-series for single device and metric. Returns [{'timestamp': ..., 'value': ...}, ...]"""
    rows = []
    for r in cleaned_records:
        if r.get('device') != device:
            continue
        v = (r.get('parsed') or {}).get(metric)
        if v is not None and isinstance(v, (int, float)):
            rows.append({
                'timestamp': r.get('timestamp') or r.get('recorded_at'),
                'value': v,
            })
    return rows


# ---------------------------------------------------------------------------
# Load from database and clean (depends on database module)
# ---------------------------------------------------------------------------

def load_and_clean_from_db(
    db,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Load latest limit records from TestDatabase and clean. db must have fetch_latest_records(limit)."""
    records = db.fetch_latest_records(limit=limit)
    return clean_records(records)


# ---------------------------------------------------------------------------
# Optional: Pandas DataFrame output for Streamlit charts/tables
# ---------------------------------------------------------------------------

def to_dataframes(
    cleaned_records: List[Dict[str, Any]],
    value_keys: Optional[List[str]] = None,
):
    """
    Produce Pandas DataFrames if pandas installed.
    time_series: long format with device, timestamp, metric, value.
    records: cleaned records as DataFrame. Falls back to dict list if no pandas.
    """
    try:
        import pandas as pd
    except ImportError:
        clean_logger.warning("pandas not installed, returning list")
        ts_rows = to_time_series_rows(cleaned_records, value_keys=value_keys)
        return {'time_series': ts_rows, 'records': cleaned_records}
    if value_keys is None:
        value_keys = ['cpu', 'memory', 'version', 'vlan', 'interfaces_summary']
    ts_rows = to_time_series_rows(cleaned_records, value_keys=value_keys)
    return {
        'time_series': pd.DataFrame(ts_rows) if ts_rows else pd.DataFrame(),
        'records': pd.DataFrame(cleaned_records),
    }
