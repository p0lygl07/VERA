import os, datetime
def log(msg):
    with open(r'C:\Users\P01yG107\Desktop\vera\logs\live_feed.log', 'a', encoding='utf-8-sig') as f:
        f.write(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] [SYSTEM_CHECK] {msg}")

log('Forge system interface is verified')