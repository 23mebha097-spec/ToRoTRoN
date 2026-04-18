
import sys
import os
sys.path.append(os.getcwd())
from PyQt5 import QtWidgets
import traceback

def test():
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow() # Mock window
    
    # Mocking Robot and SerialManager if needed, but let's try real ones first
    from core.robot import Robot
    from core.serial_manager import SerialManager
    
    class MockMainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.robot = Robot()
            self.serial_mgr = SerialManager(self)
            self.enable_3d = False
            self.current_speed = 50
            # Adding minially required attributes for panels
            from ui.panels.align_panel import AlignPanel
            from ui.panels.joint_panel import JointPanel
            from ui.panels.matrices_panel import MatricesPanel
            from ui.panels.simulation_panel import SimulationPanel
            from ui.panels.gripper_panel import GripperPanel
            
            print("Initializing AlignPanel...")
            self.align_tab = AlignPanel(self)
            print("Initializing JointPanel...")
            self.joint_tab = JointPanel(self)
            print("Initializing SimulationPanel...")
            self.simulation_tab = SimulationPanel(self)
            print("Initializing GripperPanel...")
            self.gripper_tab = GripperPanel(self)
            print("All panels initialized!")

    try:
        mw = MockMainWindow()
        print("Success!")
    except Exception:
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test()
