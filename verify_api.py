#!/usr/bin/env python3
"""
API verification script: checks that API correctly parses memory, interfaces_summary.
Run: python verify_api.py
"""
import sys

def main():
    base = "http://127.0.0.1:8000"
    
    print("=" * 60)
    print("API Verification Script")
    print("=" * 60)
    
    try:
        import httpx
    except ImportError:
        print("Install first: pip install httpx")
        sys.exit(1)
    
    # 1. Health check
    print("\n1. Checking /health ...")
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        h = r.json()
        print(f"   status: {h.get('status')}")
        print(f"   parsers_ok: {h.get('parsers_ok')}")
        print(f"   parsers: {h.get('parsers', [])}")
        if not h.get("parsers_ok"):
            print("\n   ❌ API parsers incomplete! Run:")
            print("      bash /home/wner/switch/restart_all.sh")
            print("   Or visit:", f"{base}/reload-parsers")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Cannot connect to API: {e}")
        print("   Ensure API is running: uvicorn api:app --port 8000")
        sys.exit(1)
    
    # 2. Get token
    print("\n2. Getting token ...")
    try:
        r = httpx.post(
            f"{base}/token",
            data={"username": "admin", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )
        if r.status_code != 200:
            print(f"   ❌ Login failed: {r.status_code}")
            sys.exit(1)
        token = r.json().get("access_token")
        print("   ✓ Token obtained")
    except Exception as e:
        print(f"   ❌ Login failed: {e}")
        sys.exit(1)
    
    # 3. Check time_series
    print("\n3. Checking /time_series metrics...")
    try:
        r = httpx.get(
            f"{base}/time_series",
            params={"limit": 10, "metrics": "cpu,memory,version,vlan,interfaces_summary"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if r.status_code != 200:
            print(f"   ❌ Time-series fetch failed: {r.status_code}")
            sys.exit(1)
        data = r.json()
        rows = data.get("rows", [])
        
        from collections import defaultdict
        by_metric = defaultdict(list)
        for row in rows:
            by_metric[row.get("metric")].append(row.get("value"))
        
        for m in ["cpu", "memory", "version", "vlan", "interfaces_summary"]:
            vals = by_metric.get(m, [])
            if vals:
                print(f"   {m}: ✓ {len(vals)} rows, sample={vals[:3]}...")
            else:
                print(f"   {m}: ❌ No data")
        
        if not by_metric.get("memory") or not by_metric.get("interfaces_summary"):
            print("\n   ❌ memory or interfaces_summary has no data!")
            print("   Visit:", f"{base}/reload-parsers")
            print("   Then in Streamlit click 'Reload API parsers' and 'Reload data'")
            sys.exit(1)
            
    except Exception as e:
        print(f"   ❌ Check failed: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ API verification passed! memory, interfaces_summary parsed correctly.")
    print("=" * 60)

if __name__ == "__main__":
    main()
