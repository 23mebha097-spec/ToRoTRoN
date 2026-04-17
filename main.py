import sys
import os
import time
import subprocess
from pathlib import Path
from PyQt5 import QtWidgets
from ui.main_window import MainWindow

import traceback


WATCH_EXTENSIONS = {".py", ".qss", ".ui"}
WATCH_IGNORE_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache"}

def exception_handler(exctype, value, tb):
    """Global exception handler for the GUI to prevent silent exits."""
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"CRASH DETECTED:\n{err_msg}")
    
    # Show a friendly dialog if app is running
    app = QtWidgets.QApplication.instance()
    if app:
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText("🚀 ToRoTRoN Exception")
        msg.setInformativeText("The application encountered an unexpected error during simulation.")
        msg.setDetailedText(err_msg)
        msg.setWindowTitle("System Crash Recovery")
        msg.exec_()
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_handler


def _iter_watch_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in WATCH_IGNORE_DIRS]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path.suffix.lower() in WATCH_EXTENSIONS:
                yield file_path


def _snapshot_files(root: Path):
    snapshot = {}
    for file_path in _iter_watch_files(root):
        try:
            snapshot[str(file_path)] = file_path.stat().st_mtime
        except OSError:
            continue
    return snapshot


def _has_changes(old_snapshot, new_snapshot):
    old_keys = set(old_snapshot)
    new_keys = set(new_snapshot)
    if old_keys != new_keys:
        return True
    for key, old_mtime in old_snapshot.items():
        if new_snapshot.get(key) != old_mtime:
            return True
    return False


def run_with_watch_mode():
    project_root = Path(__file__).resolve().parent
    child_args = [arg for arg in sys.argv[1:] if arg != "--watch"]

    print("[watch] Auto-reload mode enabled.")
    print("[watch] Watching source files for changes...")

    while True:
        baseline = _snapshot_files(project_root)
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *child_args])

        try:
            while child.poll() is None:
                time.sleep(1.0)
                current = _snapshot_files(project_root)
                if _has_changes(baseline, current):
                    print("[watch] Change detected. Restarting application...")
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                    break

            # If app exits without a file change, propagate its exit code.
            if child.poll() is not None and child.returncode is not None:
                # If the process was terminated by the watcher, continue loop.
                if child.returncode not in (0, 1):
                    return child.returncode

                current = _snapshot_files(project_root)
                if not _has_changes(baseline, current):
                    return child.returncode
        except KeyboardInterrupt:
            print("\n[watch] Stopping auto-reload mode...")
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
            return 0

def main():
    print("[1/3] Initializing Application...")
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    
    no_3d = ("--no-3d" in sys.argv) or (os.getenv("TOROTRON_NO_3D", "").strip().lower() in {"1", "true", "yes", "on"})

    print("[2/3] Loading UI...")
    try:
        window = MainWindow(enable_3d=not no_3d)
        window.show()
        
        print("[3/3] Application Ready.")
        sys.exit(app.exec_())
    except Exception:
        # Final catch-all for init phase
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if "--watch" in sys.argv:
        sys.exit(run_with_watch_mode())
    main()
