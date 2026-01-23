import sys
from PyQt5 import QtWidgets
from ui.main_window import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Set app-wide style
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
