# Implementation Plan - Programmable 3-D Robotic Assembly and Control Environment (ToRoTRoN)

## Project Overview
A Python-based desktop application for building, assembling, and programming robotic arms from STEP files using a frame-based kinematic engine (without URDF).

## Technical Stack
- **UI**: PyQt5
- **3D Visualization**: PyVista + PyVistaQt (VTK-based)
- **Math**: NumPy (4x4 Homogeneous Transformation Matrices)
- **Geometry**: Trimesh (for mesh handling and potentially STEP conversion if backends allow)

## Phases

### Phase 1: Base Application & 3D Environment
- [ ] Create basic PyQt5 window layout with side panels and a central 3D view.
- [ ] Integrate `pyvistaqt` background plotter into the UI.
- [ ] Implement a basic "Add Link" functionality (initially focusing on STL/STEP imports).
- [ ] Implement 3D axes and grid.

### Phase 2: Link & Assembly System (Align)
- [ ] Define `Link` data class (mesh, matrix, parent/child info).
- [ ] Implement "Link Management" panel (list of links, base selection).
- [ ] Implement "Align System":
    - Tool to select two links.
    - Gizmo/Sliders for relative T_offset adjustment.
    - Save alignment to link metadata.

### Phase 3: Kinematics Engine (Joint & Matrices)
- [ ] Define `Joint` data class (axis, origin, limits, current value).
- [ ] Implement "Joint Builder" UI:
    - Select parent/child links.
    - Set joint origin and axis (X, Y, Z).
- [ ] Implement the Matrix Engine:
    - Forward Kinematics solver using chained 4x4 matrices.
    - "Matrices" panel to display T01, T12... T0n.

### Phase 4: Programming & Control System
- [ ] Implement a basic code editor widget.
- [ ] Create a "Robot Controller" class to parse and execute commands.
- [ ] Animation loop to update the 3D pose based on command execution.
- [ ] Example commands: `move_joint(name, value)`, `move_xyz(x, y, z)`.

### Phase 5: Polish & Advanced Features
- [ ] Interaction improvements (hover effects, selection outlines).
- [ ] Export/Save project state.
- [ ] Documentation and example robot setup.

## Next Steps
1. Create the project directory structure.
2. Initialize the main PyQt5 window with PyVistaQt.
3. Implement a basic STL/STEP loader.
