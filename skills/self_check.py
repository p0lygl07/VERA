import os, datetime
def log(msg):
    with open(r'C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log', 'a', encoding='utf-8-sig') as f:
        f.write(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] [SELF_CHECK] {msg}")

log('FORGE_TEST_SUCCESS')