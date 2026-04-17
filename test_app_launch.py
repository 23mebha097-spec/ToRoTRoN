#!/usr/bin/env python3
"""
Simple test to verify the application loads without crashing
"""
import sys
import os

# Set environment variable to suppress VTK warnings
os.environ['VTK_LOGGING_LEVEL'] = 'ERROR'

from PyQt5 import QtWidgets, QtCore
import traceback

def test_app_launch():
    """Test if the app launches without crashing"""
    print("[TEST] Launching ToRoTRoN Application...")

    try:
        app = QtWidgets.QApplication(sys.argv)
        print("[STEP 1/4] QApplication created")

        from ui.main_window import MainWindow
        print("[STEP 2/4] MainWindow imported")

        window = MainWindow(enable_3d=True)
        print("[STEP 3/4] MainWindow instance created")

        # Schedule auto-exit after 2 seconds to prevent blocking
        QtCore.QTimer.singleShot(2000, app.quit)

        window.show()
        print("[STEP 4/4] Window shown, starting event loop...")

        result = app.exec_()

        if result == 0:
            print("\n[SUCCESS] Application launched and ran without crashing!")
            return True
        else:
            print(f"\n[WARNING] App exited with code {result}")
            return False

    except Exception as e:
        print(f"\n[ERROR] Application failed to launch:")
        print(f"Exception: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_app_launch()
    sys.exit(0 if success else 1)
