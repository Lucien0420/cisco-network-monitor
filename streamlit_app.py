"""
Streamlit dashboard: fetches cleaned data from FastAPI and displays tables and time-series charts.
Requires login (credentials must match API ADMIN_USER/ADMIN_PWD). Start API first: uvicorn api:app --port 8000
"""
import httpx
import streamlit as st
import pandas as pd

# When using monitor.switch.test, API should be on same host :8000
DEFAULT_API_BASE = "http://127.0.0.1:8000"


def fetch_json(base: str, path: str, params: dict = None, token: str = None):
    """Send GET to FastAPI with optional Bearer token."""
    url = base.rstrip("/") + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.get(url, params=params or {}, headers=headers or None, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Request failed {url}: {e}")
        return None


def login_for_token(base: str, username: str, password: str) -> str | None:
    """POST /token, returns access_token or None."""
    url = base.rstrip("/") + "/token"
    try:
        r = httpx.post(
            url,
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
        if r.status_code != 200:
            return None
        return r.json().get("access_token")
    except Exception:
        return None


st.set_page_config(page_title="Switch Monitor Dashboard", page_icon="📊", layout="wide")

# Custom CSS to fix the red border and improve UI
st.markdown("""
    <style>
    /* Remove the red border from multiselect */
    .stMultiSelect [data-baseweb="select"] {
        border-color: #e0e0e0 !important;
    }
    /* Change tag background from red to professional blue */
    span[data-baseweb="tag"] {
        background-color: #1c83e1 !important;
        color: white !important;
    }
    /* Improve button styling */
    .stButton>button {
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# Not logged in: show login form
if "access_token" not in st.session_state:
    st.title("🔐 Login")
    st.caption("Use the same credentials as API (ADMIN_USER / ADMIN_PWD)")
    with st.form("login"):
        api_base = st.text_input("API URL", value=DEFAULT_API_BASE)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if not username or not password:
                st.error("Please enter username and password")
            else:
                token = login_for_token(api_base, username, password)
                if token:
                    st.session_state["access_token"] = token
                    st.session_state["api_base"] = api_base
                    st.rerun()
                else:
                    st.error("Invalid credentials or API unreachable")
    st.stop()

# Logged in: dashboard
token = st.session_state["access_token"]
api_base = st.session_state.get("api_base", DEFAULT_API_BASE)

# --- INITIAL STATE ---
if "limit" not in st.session_state:
    st.session_state["limit"] = 500

# Health check (no token required)
health = fetch_json(api_base, "/health")
if not health or health.get("status") != "ok":
    st.warning("Cannot connect to API. Ensure it is running: `uvicorn api:app --reload`")
    st.stop()
if not health.get("parsers_ok", True):
    st.warning("⚠️ API parsers outdated (missing memory/interfaces_summary). Run `bash restart_all.sh`.")

# --- DATA FETCHING ---
cleaned_res = fetch_json(api_base, "/cleaned", params={"limit": st.session_state["limit"]}, token=token)
ts_res = fetch_json(api_base, "/time_series", params={"limit": st.session_state["limit"], "metrics": "cpu,memory,version,vlan,interfaces_summary"}, token=token)

if not cleaned_res:
    st.error("Failed to fetch data (token may have expired, please login again)")
    st.stop()

raw_records = cleaned_res.get("records", [])
raw_ts_rows = (ts_res or {}).get("rows", []) if ts_res else []
# -------------------------------------------------------

with st.sidebar:
    st.header("Settings")
    st.caption("For monitor.switch.test, use http://monitor.switch.test:8000")
    api_base_input = st.text_input("API URL", value=api_base, key="api_base_input")
    st.session_state["api_base"] = api_base_input
    limit = st.number_input("Record limit", min_value=10, max_value=5000, value=st.session_state["limit"], step=50, key="limit_input")
    st.session_state["limit"] = limit
    
    st.divider()
    st.subheader("Device Filter")
    
    # Get unique devices from raw_records
    all_devices = sorted(list(set([r.get("device") for r in raw_records if r.get("device")])))
    
    if all_devices:
        # Initialize widget state if not present
        if "device_selector_widget" not in st.session_state:
            st.session_state["device_selector_widget"] = all_devices

        col1, col2 = st.columns(2)
        if col1.button("Select All", use_container_width=True):
            st.session_state["device_selector_widget"] = all_devices
            st.rerun()
        if col2.button("Clear All", use_container_width=True):
            st.session_state["device_selector_widget"] = []
            st.rerun()
            
        # Use the widget key directly for state management
        selected_devices = st.multiselect(
            "Show devices",
            options=all_devices,
            key="device_selector_widget"
        )
    else:
        selected_devices = []

    st.divider()
    if st.button("🔄 Reload data", use_container_width=True):
        st.rerun()
    if st.button("🔧 Reload API parsers", use_container_width=True, help="If memory/interfaces_summary charts are empty, click this then reload"):
        try:
            import httpx
            resp = httpx.get(api_base.rstrip("/") + "/reload-parsers", timeout=5)
            if resp.status_code == 200:
                r = resp.json()
                if r.get("status") == "ok":
                    st.success("Parsers reloaded. Click 'Reload data'.")
                else:
                    st.error("Reload failed")
            elif resp.status_code == 404:
                st.warning("API has no /reload-parsers. Run `bash restart_all.sh` to restart API.")
            else:
                st.error(f"Reload failed ({resp.status_code})")
        except Exception as e:
            st.error(f"Request failed: {e}")
    if st.button("🚪 Logout", use_container_width=True):
        del st.session_state["access_token"]
        if "api_base" in st.session_state:
            del st.session_state["api_base"]
        st.rerun()

st.title("📊 Switch Monitor Dashboard")
st.caption("Data source: FastAPI (JWT) → SQLite + data_cleaning")

# Filter data based on selected devices from sidebar
selected_devices = st.session_state.get("device_selector_widget", [])
if selected_devices:
    records = [r for r in raw_records if r.get("device") in selected_devices]
    ts_rows = [r for r in raw_ts_rows if r.get("device") in selected_devices]
elif all_devices: # If nothing selected but devices exist, show nothing
    records = []
    ts_rows = []
else:
    records = raw_records
    ts_rows = raw_ts_rows

st.success(f"Loaded **{len(records)}** filtered records, **{len(ts_rows)}** time-series rows.")

if records:
    df = pd.DataFrame(records)
    # Flatten parsed into separate columns so memory, interfaces_summary etc. are visible
    numeric_keys = ["cpu", "memory", "version", "vlan", "interfaces_summary"]
    if "parsed" in df.columns:
        df = df.copy()
        for k in numeric_keys:
            df[k] = df["parsed"].apply(
                lambda p, key=k: p.get(key) if isinstance(p, dict) and p else None
            )
    display_cols = [c for c in ["id", "device", "iteration", "timestamp", "elapsed_time"] + numeric_keys if c in df.columns]
    st.subheader("Cleaned records (latest)")
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True, height=300)

if ts_rows:
    st.subheader("Time-series (CPU / Memory / Version / VLAN / Interfaces)")
    ts_df = pd.DataFrame(ts_rows)
    if not ts_df.empty and "timestamp" in ts_df.columns and "value" in ts_df.columns:
        ts_df["timestamp"] = pd.to_datetime(ts_df["timestamp"], errors="coerce")
        ts_df = ts_df.dropna(subset=["timestamp"])
        # Show all 5 metrics even if API parsing is incomplete
        requested_metrics = ["cpu", "memory", "version", "vlan", "interfaces_summary"]
        if "metric" in ts_df.columns:
            data_metrics = [m for m in ts_df["metric"].dropna().unique().tolist() if str(m).strip()]
            metric_options = list(dict.fromkeys(requested_metrics + data_metrics))
        else:
            metric_options = requested_metrics
        if not metric_options:
            metric_options = ["value"]
        # Preserve metric selection across reloads
        if "selected_metric" not in st.session_state:
            st.session_state["selected_metric"] = "cpu"
        idx = metric_options.index(st.session_state["selected_metric"]) if st.session_state["selected_metric"] in metric_options else 0
        chosen = st.selectbox("Select metric", metric_options, index=idx, key="metric_selector")
        st.session_state["selected_metric"] = chosen
        sub = (ts_df[ts_df["metric"] == chosen].copy() if "metric" in ts_df.columns else ts_df.copy())
        
        # Ensure numeric values (use .loc to avoid SettingWithCopyWarning)
        sub.loc[:, "value"] = pd.to_numeric(sub["value"], errors="coerce")

        if not sub.empty:
            sub = sub.sort_values("timestamp")
            # Show value range for verification
            val_min, val_max = sub["value"].min(), sub["value"].max()
            st.caption(f"📊 {chosen} range: {val_min:.2f} ~ {val_max:.2f} ({len(sub)} rows) | 💡 Drag chart to zoom/pan")
            # Use Altair with explicit data binding and interactive zoom/pan
            import altair as alt
            chart = (
                alt.Chart(sub)
                .mark_line()
                .encode(
                    x=alt.X("timestamp:T", title="Time"),
                    y=alt.Y("value:Q", title=chosen),
                    color="device:N",
                )
                .properties(height=350)
                .interactive()  # Enable zoom and pan on x-axis
            )
            st.altair_chart(chart, use_container_width=True, key=f"chart_{chosen}")
        else:
            st.info("No data to plot.")
            if chosen in ("memory", "interfaces_summary"):
                st.caption("💡 If memory/interfaces_summary empty: run `bash restart_all.sh` to reload parsers.")
    else:
        st.info("Time-series format invalid or no numeric values.")
else:
    st.info("No time-series data yet (requires numeric parsed fields: cpu, memory, etc.).")

# Interface status and VLAN list (latest record per device)
if records:
    by_device = {}
    for r in records:
        dev = r.get("device", "")
        if dev and dev not in by_device:
            by_device[dev] = r
    for device, rec in by_device.items():
        parsed = rec.get("parsed") or {}
        interfaces = parsed.get("interfaces")
        vlan_list = parsed.get("vlan_list")
        if isinstance(interfaces, list) and interfaces or isinstance(vlan_list, list) and vlan_list:
            with st.expander(f"📋 {device} - Interface status & VLAN list (latest snapshot)"):
                if isinstance(interfaces, list) and interfaces:
                    st.subheader("Interface status")
                    if_data = [
                        {"Port": x.get("port", x.get("interface", "")), "Name": x.get("name", ""), "Status": x.get("status", ""), "VLAN": x.get("vlan", ""), "Duplex": x.get("duplex", ""), "Speed": x.get("speed", "")}
                        for x in interfaces
                    ]
                    st.dataframe(pd.DataFrame(if_data), use_container_width=True, height=min(250, 50 + len(if_data) * 35))
                if isinstance(vlan_list, list) and vlan_list:
                    st.subheader("VLAN list")
                    vlan_data = [{"VLAN ID": x.get("vlan_id", ""), "Name": x.get("name", ""), "Status": x.get("status", ""), "Ports": x.get("ports", "")} for x in vlan_list]
                    st.dataframe(pd.DataFrame(vlan_data), use_container_width=True, height=min(250, 50 + len(vlan_data) * 35))

with st.expander("Configured devices (devices.json)"):
    dev_res = fetch_json(api_base, "/devices", token=token)
    if dev_res and dev_res.get("devices"):
        st.json(dev_res["devices"])
    else:
        st.write("No devices or read failed.")
