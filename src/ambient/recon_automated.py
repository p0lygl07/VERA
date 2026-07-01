import psutil, datetime, os

def log_to_feed(msg):
    log_path = r"C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    # Open in append-binary ('ab') mode to allow unbuffered writes (buffering=0)
    with open(log_path, 'ab', buffering=0) as f:
        # Encode string to bytes before writing
        f.write(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}".encode('utf-8'))

if __name__ == "__main__":
    log_to_feed("--- VERA RECON_AUTOMATED INITIALIZED ---")
    
    # Simple check for psutil
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        log_to_feed(f"System Health Check: CPU {cpu_usage}%")
    except Exception as e:
        log_to_feed(f"Health Check Failed: {e}")

    # Mock Recon Workflow
    targets = ["localhost"]
    for target in targets:
        log_to_feed(f"Scanning Target: {target}")
        log_to_feed("Running: subfinder -d " + target)
        log_to_feed("Running: httpx -target " + target)
        log_to_feed("Execution Complete: No critical vulnerabilities.")
