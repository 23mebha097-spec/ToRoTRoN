import vtk
print("VTK version:", vtk.vtkVersion.GetVTKVersion())
try:
    renderer = vtk.vtkRenderer()
    renderWindow = vtk.vtkRenderWindow()
    renderWindow.AddRenderer(renderer)
    renderWindowInteractor = vtk.vtkRenderWindowInteractor()
    renderWindowInteractor.SetRenderWindow(renderWindow)
    renderWindow.Render()
    print("VTK Rendering SUCCESSFUL (off-screen or minimal window).")
except Exception as e:
    print(f"VTK Rendering FAILED: {e}")
