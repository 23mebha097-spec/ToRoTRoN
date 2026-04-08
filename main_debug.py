import sys, os, traceback
print("--- [DEBUG] DEBUGGING main.py STARTUP ---")
try:
    print("[1] Imports...")
    from PyQt5 import QtWidgets, QtCore, QtGui
    print("[1.1] Robot...")
    from core.robot import Robot
    print("[1.2] MainWindow...")
    from ui.main_window import MainWindow
    
    print("[2] Init QApplication...")
    app = QtWidgets.QApplication(sys.argv)
    
    print("[3] Init MainWindow...")
    window = MainWindow()
    
    print("[4] Show UI...")
    window.show()
    
    print("[5] Event Loop Start...")
    sys.exit(app.exec_())
except Exception:
    print("--- [DEBUG] CRASH DETECTED ---")
    traceback.print_exc()
    sys.exit(1)
