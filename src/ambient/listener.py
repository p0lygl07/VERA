import time, os
path = r'C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log'
print("--- VERA LINK ACTIVE (SIG-SAFE) ---")
last_seen = ""
while True:
    if os.path.exists(path):
        # 'utf-8-sig' automatically handles files that have BOM headers
        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            if content != last_seen:
                print(content)
                last_seen = content
    time.sleep(1)