import time, os, sys
from bridge_agent import monitor_and_reason, reason_and_act

def log_alert(msg):
    """Log project alerts alongside live feed"""
    alert_path = r"C:\Users\p0ly\Desktop\AI\VERA\logs\project_alerts.log"
    with open(alert_path, 'a', encoding='utf-8-sig') as f:
        f.write(f"\n[{time.strftime('%H:%M:%S')}] [ALERT] {msg}\n")

def main():
    log_path = r"C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log"
    
    print("--- VERA WATCH INITIALIZED ---")
    print(f"Monitoring: {log_path}")
    print("Alerts will be logged to: project_alerts.log\n")
    
    # Start monitoring loop with bridge_agent integration
    monitor_and_reason()

if __name__ == "__main__":
    main()