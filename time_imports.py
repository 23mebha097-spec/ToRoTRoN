import time
import sys
import os

print("Starting imports (selective)...")
start = time.time()

try:
    import vtkmodules.vtkRenderingCore as vtkRenderingCore
    import vtkmodules.vtkCommonCore as vtkCommonCore
    print(f"VTK selective modules imported in {time.time() - start:.2f}s")
    
    start = time.time()
    import pyvista as pv
    print(f"PyVista imported in {time.time() - start:.2f}s")
    
    start = time.time()
    from PyQt5 import QtWidgets, QtCore
    print(f"PyQt5 imported in {time.time() - start:.2f}s")
    
    start = time.time()
    from ui.main_window import MainWindow
    print(f"MainWindow imported in {time.time() - start:.2f}s")
    
    print("All imports successful")
    
except Exception as e:
    print(f"Error during import: {e}")
    import traceback
    traceback.print_exc()
except KeyboardInterrupt:
    print("\nImport interrupted by user")
