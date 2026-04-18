
import sys
import os
sys.path.append(os.getcwd())
from PyQt5 import QtWidgets
import traceback

def test():
    app = QtWidgets.QApplication(sys.argv)
    try:
        print("Importing RobotCanvas...")
        from graphics.canvas import RobotCanvas
        print("Initializing RobotCanvas...")
        # RobotCanvas needs to be offscreen or we need a fake display if it's headless
        # But let's see if it even gets past __init__
        canvas = RobotCanvas()
        print("Success!")
    except Exception:
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test()
