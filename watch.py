from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time
import sys

class Handler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.restart_program()

    def restart_program(self):
        if self.process:
            self.process.kill()
        print("\n----- Restarting app.py -----\n")
        self.process = subprocess.Popen([sys.executable, 'app.py'])

    def on_modified(self, event):
        if event.src_path.endswith('app.py'):
            self.restart_program()

if __name__ == "__main__":
    handler = Handler()
    observer = Observer()
    observer.schedule(handler, path='.', recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if handler.process:
            handler.process.kill()
    observer.join() 