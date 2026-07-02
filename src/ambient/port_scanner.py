import socket, datetime, sys


def log(msg):
    log_path = r"C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log"
    # Use 'w' or 'a' with encoding='utf-8' to ensure clear text output
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] [SCANNER] {msg}")


def scan(target, ports):
    log(f"Starting scan on {target}...")
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((target, port)) == 0:
                log(f"PORT {port} IS OPEN")
    log("Scan complete.")


def main():
    target_host = "127.0.0.1"
    # Ports to check: HTTP, HTTPS, Ollama, Custom
    ports_to_check = [80, 443, 11434, 8080]
    scan(target_host, ports_to_check)


if __name__ == "__main__":
    main()
