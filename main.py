import sys
import os
from PyQt5 import QtWidgets
from ui.main_window import MainWindow

import traceback

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
    main()
