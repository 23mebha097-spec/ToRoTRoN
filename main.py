import sys
from PyQt5 import QtWidgets
from ui.main_window import MainWindow

def main():
    print("[1/3] Initializing Application...")
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    
    print("[2/3] Loading 3D Engine & UI...")
    window = MainWindow()
    window.show()
    
    print("[3/3] Application Ready.")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
