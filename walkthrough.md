# ToRoTRoN Walkthrough

## How to use the Programmable 3-D Robotic Assembly Environment

### 1. Importing Links
- Go to the **Links** tab.
- Click **Import STEP/STL**.
- Select your mesh files. They will appear in the 3D view at the origin (0,0,0).
- Select one link and click **Set as Base**. This will be the root of your robot.

### 2. Aligning Parts (The "Assembly" Phase)
- Switch to the **Align** tab.
- Select a **Parent Link** (e.g., the Base) and a **Child Link** (e.g., Link 1).
- Use the **Translation (X, Y, Z)** and **Rotation (Roll, Pitch, Yaw)** sliders to position the child link relative to the parent.
- Click **Show Preview** to see the adjustment.
- Once satisfied, click **Save Alignment**. This locks the "zero position" transform between these two links.

### 3. Creating Joints (The "Kinematics" Phase)
- Switch to the **Joint** tab.
- Select the **Parent** and **Child** links.
- Set the **Joint Axis** (default is Z-axis: 0, 0, 1).
- Click **Create Joint**.
- You can now select the joint in the list and use the slider to **Rotate** it and see the robot move.

### 4. Inspecting Matrices
- Switch to the **Matrices** tab.
- Click **Update Matrices** to see the 4x4 homogeneous transformation matrices for every joint and the world transform for every link.
- This is the core "Kinematics Core" mentioned in the specs.

### 5. Programming the Robot
- Switch to the **Code** tab.
- Write commands like:
  ```
  JOINT Joint_1 45
  WAIT 1.0
  JOINT Joint_1 -45
  ```
- Click **RUN PROGRAM**. The robot will animate according to your code.

## Internal Engineering
- All calculations use **NumPy**.
- Visualization is handled by **VTK** via **PyVista**.
- UI is built with **PyQt5**.
- Kinematics follow a tree-traversal matrix multiplication: $T_{child\_world} = T_{parent\_world} \times T_{joint} \times T_{offset}$.
