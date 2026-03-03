from PyQt5 import QtWidgets
import os
import numpy as np

from core.robot import Robot


class ProjectMixin:
    """Methods for saving and loading robot project files (.trn)."""

    def save_project(self):
        """Saves current robot configuration into a .trn zip file."""
        import json
        import zipfile
        import io
        import tempfile
        import shutil

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Project", "", "ToRoTRoN Project (*.trn)"
        )
        if not file_path:
            return
            
        if not file_path.endswith('.trn'):
            file_path += '.trn'

        try:
            # Create a temporary directory to gather files
            with tempfile.TemporaryDirectory() as temp_dir:
                mesh_dir = os.path.join(temp_dir, "meshes")
                os.makedirs(mesh_dir)

                robot_data = {
                    "links": [],
                    "joints": [],
                    "ui_state": {
                        "joint_panel_joints": {},
                        "program_code": "",
                        "live_sync": False,
                        "alignment_point": None,
                        "alignment_normal": None
                    }
                }

                # 1. Gather Links
                for name, link in self.robot.links.items():
                    mesh_filename = f"{name}.stl"
                    mesh_path = os.path.join(mesh_dir, mesh_filename)
                    
                    # Export mesh
                    link.mesh.export(mesh_path, file_type='stl')
                    
                    robot_data["links"].append({
                        "name": link.name,
                        "mesh_file": f"meshes/{mesh_filename}",
                        "color": link.color,
                        "is_base": link.is_base,
                        "t_offset": link.t_offset.tolist()
                    })

                # 2. Gather Joints (Robot Core)
                for name, joint in self.robot.joints.items():
                    robot_data["joints"].append({
                        "name": joint.name,
                        "parent_link": joint.parent_link.name,
                        "child_link": joint.child_link.name,
                        "joint_type": joint.joint_type,
                        "origin": joint.origin.tolist(),
                        "axis": joint.axis.tolist(),
                        "min_limit": joint.min_limit,
                        "max_limit": joint.max_limit,
                        "current_value": joint.current_value
                    })

                # 3. Gather UI State
                # Joint Panel UI Data
                if hasattr(self, 'joint_tab'):
                    for child_name, data in self.joint_tab.joints.items():
                        clean_data = data.copy()
                        if 'alignment_point' in clean_data and isinstance(clean_data['alignment_point'], np.ndarray):
                            clean_data['alignment_point'] = clean_data['alignment_point'].tolist()
                        robot_data["ui_state"]["joint_panel_joints"][child_name] = clean_data

                # Program Tab Code
                if hasattr(self, 'program_tab'):
                    robot_data["ui_state"]["program_code"] = self.program_tab.code_edit.toPlainText()
                    robot_data["ui_state"]["live_sync"] = self.program_tab.sync_hw_check.isChecked()

                # Align Panel Stored Point (for continuing joint creation)
                if hasattr(self, 'align_tab'):
                    if hasattr(self.align_tab, 'alignment_point') and self.align_tab.alignment_point is not None:
                        robot_data["ui_state"]["alignment_point"] = self.align_tab.alignment_point.tolist()
                    if hasattr(self.align_tab, 'alignment_normal') and self.align_tab.alignment_normal is not None:
                        robot_data["ui_state"]["alignment_normal"] = self.align_tab.alignment_normal.tolist()

                # 4. Write JSON
                json_path = os.path.join(temp_dir, "robot.json")
                with open(json_path, 'w') as f:
                    json.dump(robot_data, f, indent=4)

                # 4. ZIP everything up
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            abs_file = os.path.join(root, file)
                            rel_file = os.path.relpath(abs_file, temp_dir)
                            zipf.write(abs_file, rel_file)

            self.log(f"Project saved to: {file_path}")
            QtWidgets.QMessageBox.information(self, "Success", "Project saved successfully.")

        except Exception as e:
            self.log(f"SAVE ERROR: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Could not save project: {str(e)}")

    def load_project(self):
        """Loads a robot configuration from a .trn zip file."""
        import json
        import zipfile
        import tempfile
        import shutil
        import trimesh

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Project", "", "ToRoTRoN Project (*.trn)"
        )
        if not file_path:
            return

        try:
            # 1. Clear Current Robot
            self.robot = Robot()
            self.canvas.clear_highlights()
            # Remove all actors from canvas
            actor_names = list(self.canvas.actors.keys())
            for name in actor_names:
                self.canvas.remove_actor(name)
            self.canvas.fixed_actors.clear()
            self.links_list.clear()

            # Reset UI Panels
            if hasattr(self, 'joint_tab'): self.joint_tab.reset_joint_ui()
            if hasattr(self, 'align_tab'): self.align_tab.reset_panel()

            # 2. Extract ZIP to temp folder
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(file_path, 'r') as zipf:
                    zipf.extractall(temp_dir)

                # 3. Read JSON
                json_path = os.path.join(temp_dir, "robot.json")
                if not os.path.exists(json_path):
                    raise Exception("Invalid project file: robot.json missing")

                with open(json_path, 'r') as f:
                    robot_data = json.load(f)

                # 4. Load Links
                for l_data in robot_data["links"]:
                    name = l_data["name"]
                    mesh_rel_path = l_data["mesh_file"]
                    mesh_path = os.path.join(temp_dir, mesh_rel_path)
                    
                    if not os.path.exists(mesh_path):
                        self.log(f"WARNING: Mesh file missing for {name}")
                        continue

                    mesh = trimesh.load(mesh_path)
                    link = self.robot.add_link(name, mesh)
                    link.color = l_data.get("color", "lightgray")
                    link.is_base = l_data.get("is_base", False)
                    link.t_offset = np.array(l_data["t_offset"])
                    
                    if link.is_base:
                        self.robot.base_link = link
                        self.canvas.fixed_actors.add(name)

                    # Add to UI and Canvas
                    self.links_list.addItem(name)
                    self.canvas.update_link_mesh(name, mesh, link.t_offset, color=link.color)

                # 5. Load Joints (Robot Core)
                for j_data in robot_data["joints"]:
                    name = j_data["name"]
                    parent_name = j_data["parent_link"]
                    child_name = j_data["child_link"]
                    
                    if parent_name in self.robot.links and child_name in self.robot.links:
                        joint = self.robot.add_joint(name, parent_name, child_name)
                        joint.joint_type = j_data.get("joint_type", "revolute")
                        joint.origin = np.array(j_data["origin"])
                        joint.axis = np.array(j_data["axis"])
                        joint.min_limit = j_data.get("min_limit", -180.0)
                        joint.max_limit = j_data.get("max_limit", 180.0)
                        joint.current_value = j_data.get("current_value", 0.0)

                # 6. Load UI State
                ui_state = robot_data.get("ui_state", {})
                
                # Restore Joint Panel Data
                if hasattr(self, 'joint_tab'):
                    self.joint_tab.joints = ui_state.get("joint_panel_joints", {})
                    # Convert alignment points back to numpy
                    for child_name, data in self.joint_tab.joints.items():
                        if 'alignment_point' in data and data['alignment_point'] is not None:
                            data['alignment_point'] = np.array(data['alignment_point'])
                    
                    self.joint_tab.refresh_joints_history()
                    self.joint_tab.refresh_links()

                # Restore Program Tab
                if hasattr(self, 'program_tab'):
                    self.program_tab.code_edit.setPlainText(ui_state.get("program_code", ""))
                    self.program_tab.sync_hw_check.setChecked(ui_state.get("live_sync", False))

                # Restore Align Panel alignment data
                if hasattr(self, 'align_tab'):
                    ap = ui_state.get("alignment_point")
                    if ap: self.align_tab.alignment_point = np.array(ap)
                    an = ui_state.get("alignment_normal")
                    if an: self.align_tab.alignment_normal = np.array(an)

            # 7. Final Update
            self.robot.update_kinematics()
            self.canvas.update_transforms(self.robot)
            self.update_link_colors()
            
            # Refresh Matrices Panel
            if hasattr(self, 'matrices_tab'):
                self.matrices_tab.refresh_sliders()
                self.matrices_tab.update_display()

            self.canvas.plotter.reset_camera()
            
            self.log(f"Project loaded from: {file_path}")
            QtWidgets.QMessageBox.information(self, "Success", "Project loaded successfully.")

        except Exception as e:
            self.log(f"LOAD ERROR: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Load Error", f"Could not load project: {str(e)}")
