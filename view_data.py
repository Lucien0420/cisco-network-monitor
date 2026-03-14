#!/usr/bin/env python3
"""
Simple data viewer - reads from database and displays records.
"""
import sqlite3
import json
from datetime import datetime

def view_data():
    conn = sqlite3.connect('data/dvt_monitor_results.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("🌐 Cisco Switch Monitor - Data Viewer")
    print("="*80)
    
    # Stats
    cursor.execute("SELECT device, COUNT(*) as count FROM monitor_records GROUP BY device ORDER BY count DESC")
    stats = cursor.fetchall()
    
    print("\n📊 Monitoring stats:")
    print("-" * 80)
    for row in stats:
        print(f"  • {row['device']}: {row['count']} records")
    
    cursor.execute("SELECT COUNT(*) as total FROM monitor_records")
    total = cursor.fetchone()['total']
    print(f"\n  Total: {total} records")
    
    # Latest DevNet data
    print("\n" + "="*80)
    print("📈 Latest DevNet Catalyst 9000 (5 records)")
    print("="*80)
    
    cursor.execute("""
        SELECT id, device, iteration, timestamp, metrics, elapsed_time 
        FROM monitor_records 
        WHERE device = 'DevNet_Catalyst9000'
        ORDER BY id DESC LIMIT 5
    """)
    
    records = cursor.fetchall()
    
    for idx, record in enumerate(records, 1):
        print(f"\n[Record #{record['id']}] iter {record['iteration']}")
        print(f"  Time: {record['timestamp']}")
        print(f"  Elapsed: {record['elapsed_time']:.2f}s")
        
        metrics = json.loads(record['metrics'] or '{}')
        print(f"  Metrics: {', '.join(metrics.keys())}")
        
        # Show first 150 chars per metric
        for metric_name, metric_value in metrics.items():
            if isinstance(metric_value, str):
                preview = metric_value[:150]
                if len(metric_value) > 150:
                    preview += f"... (+{len(metric_value) - 150} chars)"
                print(f"\n    [{metric_name}]")
                print(f"    {preview}")
    
    # CPU extraction example
    print("\n" + "="*80)
    print("📉 CPU utilization sample")
    print("="*80)
    
    cursor.execute("""
        SELECT timestamp, metrics FROM monitor_records 
        WHERE device = 'DevNet_Catalyst9000' AND metrics LIKE '%cpu%'
        ORDER BY id DESC LIMIT 3
    """)
    
    cpu_records = cursor.fetchall()
    for record in cpu_records:
        metrics = json.loads(record['metrics'])
        cpu_data = metrics.get('cpu', '')
        if cpu_data:
            # First line (CPU summary)
            first_line = cpu_data.split('\n')[0]
            print(f"  {record['timestamp']}: {first_line}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ Done")
    print("="*80 + "\n")

if __name__ == "__main__":
    try:
        view_data()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
