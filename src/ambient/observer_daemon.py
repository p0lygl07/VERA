import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class LogHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("task_stream.log"):
            with open(event.src_path, 'r') as f:
                lines = f.readlines()
                if lines:
                    print(f"\n[NEW_TASK_INPUT]: {lines[-1].strip()}")


def main():
    observer = Observer()
    handler = LogHandler()
    observer.schedule(handler, path=r'C:\Users\p0ly\Desktop\AI\VERA\logs', recursive=False)
    observer.start()
    print("Observer-Daemon Active. Monitoring task_stream.log...")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: 
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
