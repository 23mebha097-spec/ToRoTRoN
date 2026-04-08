import sys
try:
    print("Testing PyQt5...")
    from PyQt5 import QtWidgets, QtCore, QtGui
    print("Testing trimesh...")
    import trimesh
    print("Testing numpy...")
    import numpy as np
    print("Testing pyvista...")
    import pyvista
    print("Testing pyvistaqt...")
    import pyvistaqt
    print("Testing cascadio...")
    import cascadio
    print("All imports SUCCESSFUL.")
except Exception as e:
    print(f"FAILED on {e}")
    sys.exit(1)
