#!/usr/bin/env python3
"""Monitor progress of batch proposition analysis."""
import sqlite3
import time
from datetime import datetime

db_path = '/Users/arnavsharma/.cache/gum/gum.db'

print("Monitoring ambiguity analysis progress...")
print("Press Ctrl+C to stop\n")

start_count = None
start_time = time.time()

try:
    while True:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current count
        cursor.execute('SELECT COUNT(DISTINCT proposition_id) FROM ambiguity_analyses')
        current_count = cursor.fetchone()[0]
        
        # Get latest timestamp
        cursor.execute('SELECT MAX(created_at) FROM ambiguity_analyses')
        latest = cursor.fetchone()[0]
        
        conn.close()
        
        if start_count is None:
            start_count = current_count
        
        processed = current_count - start_count
        elapsed = time.time() - start_time
        rate = processed / elapsed * 60 if elapsed > 0 else 0
        
        remaining = 200 - processed if processed < 200 else 0
        eta_mins = remaining / rate if rate > 0 else 0
        
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] "
              f"Analyzed: {current_count} (+{processed} this run) | "
              f"Rate: {rate:.1f}/min | "
              f"Remaining: {remaining} | "
              f"ETA: {eta_mins:.0f}m | "
              f"Latest: {latest}", 
              end='', flush=True)
        
        time.sleep(10)
        
except KeyboardInterrupt:
    print("\n\nMonitoring stopped.")
