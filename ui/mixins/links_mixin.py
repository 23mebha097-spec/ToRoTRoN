from PyQt5 import QtWidgets, QtGui
import numpy as np
import os
import random


class LinksMixin:
    """Methods for managing robot links: import, select, base, remove, color."""

    def setup_links_tab(self):
        layout = QtWidgets.QVBoxLayout(self.links_tab)
        
        import_btn = QtWidgets.QPushButton("Import STEP/STL")
        import_btn.clicked.connect(self.import_mesh)
        layout.addWidget(import_btn)
        
        self.links_list = QtWidgets.QListWidget()
        self.links_list.itemClicked.connect(self.on_link_selected)
        layout.addWidget(self.links_list)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.set_base_btn = QtWidgets.QPushButton("Set as Base")
        self.remove_btn = QtWidgets.QPushButton("Remove")
        
        self.set_base_btn.clicked.connect(self.set_as_base)
        self.remove_btn.clicked.connect(self.remove_link)
        
        btn_layout.addWidget(self.set_base_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)

        self.color_btn = QtWidgets.QPushButton("Change Color")
        self.color_btn.clicked.connect(self.change_color)
        layout.addWidget(self.color_btn)
        
        layout.addStretch()

    def on_link_selected(self, item):
        name = item.text()
        
        # Allow all objects to be selected, including jointed ones
        # Users may need to select jointed objects to build further joints
        self.canvas.select_actor(name)
        
        # Update button text based on whether selection is the base
        if self.robot.base_link and name == self.robot.base_link.name:
            self.set_base_btn.setText("Deselect as Base")
        else:
            self.set_base_btn.setText("Set as Base")

    def set_as_base(self):
        item = self.links_list.currentItem()
        if not item:
            return
            
        name = item.text()
        if name not in self.robot.links:
            return
            
        link = self.robot.links[name]
        
        # TOGGLE LOGIC: If it's already the base, unset it
        if self.robot.base_link == link:
            self.robot.base_link = None
            link.is_base = False
            self.canvas.fixed_actors.clear()
            self.log(f"BASE UNSET: {name}. Link is now floating.")
            self.set_base_btn.setText("Set as Base")
        else:
            # 1. Calculate offset to center the mesh at (0,0,0)
            centroid = link.mesh.centroid
            
            # Create a translation matrix that moves the mesh's centroid to (0,0,0)
            t_center = np.eye(4)
            t_center[:3, 3] = -centroid
            
            # 2. Update Link Properties
            if self.robot.base_link:
                self.robot.base_link.is_base = False
                
            link.is_base = True
            link.t_offset = t_center
            
            # Base is defined at World Origin
            self.robot.base_link = link
            
            # LOCK in 3D Canvas (so it cannot be dragged)
            self.canvas.fixed_actors.clear()
            self.canvas.fixed_actors.add(name)
            self.set_base_btn.setText("Deselect as Base")
            self.log(f"BASE SET: {name}")
            self.log(f"Moved centroid {centroid} to (0,0,0)")
            self.canvas.plotter.reset_camera()
        
        # 3. Update Robot
        self.robot.update_kinematics()
        self.canvas.update_transforms(self.robot)
        
        # 4. Focus Camera
        self.update_link_colors()

    def go_to_joint_tab(self):
        item = self.links_list.currentItem()
        if not item:
            return
        
        name = item.text()
        # Switch to Joint Tab (Index 2)
        self.switch_panel(2)
        
        # Refresh links first to ensure combo boxes are up to date
        self.joint_tab.refresh_links()
        
        # Pre-select this link as the Child Link
        self.joint_tab.select_child_link(name)
        
        self.log(f"Switched to Joint creation for: {name}")

    def remove_link(self):
        item = self.links_list.currentItem()
        if not item:
            return
        
        name = item.text()
        
        # 1. Remove from Robot Model (Core)
        self.robot.remove_link(name)
        
        # 2. Cleanup and Sync Graphics state
        self.canvas.fixed_actors.clear()
        if self.robot.base_link:
            self.canvas.fixed_actors.add(self.robot.base_link.name)
        
        # Remove from Scene (Graphics)
        self.canvas.remove_actor(name)
        
        # 3. Remove from UI List
        row = self.links_list.row(item)
        self.links_list.takeItem(row)
        
        self.log(f"Removed link: {name}")
        
        # Refresh kinematics just in case
        self.robot.update_kinematics()
        self.canvas.update_transforms(self.robot)
        self.update_link_colors()

    def update_link_colors(self):
        """Updates the icons in the link list to show Base (Red) vs Normal/Joint (Green)."""
        root = self.robot.base_link
        
        # Create helper to make colored icons
        def make_icon(color_str):
            pixmap = QtGui.QPixmap(20, 20)
            pixmap.fill(QtGui.QColor(color_str))
            return QtGui.QIcon(pixmap)
            
        red_icon = make_icon("#d32f2f")   # Base Red
        green_icon = make_icon("#388e3c") # Joint Green
        
        for i in range(self.links_list.count()):
            item = self.links_list.item(i)
            name = item.text()
            
            if name in self.robot.links:
                link = self.robot.links[name]
                if link == root:
                    item.setIcon(red_icon)
                    item.setToolTip("Base Link (Fixed/Locked)")
                else:
                    item.setIcon(green_icon)
                    item.setToolTip("Joint/Child Link")

    def change_color(self):
        item = self.links_list.currentItem()
        if not item:
            return
            
        name = item.text()
        if name not in self.robot.links:
            return
            
        link = self.robot.links[name]
        initial_color = QtGui.QColor(link.color)
        
        color = QtWidgets.QColorDialog.getColor(initial_color, self, f"Select Color for {name}")
        if color.isValid():
            hex_color = color.name()
            link.color = hex_color
            if name in self.canvas.actors:
                self.canvas.set_actor_color(name, hex_color)
            self.update_link_colors()
            self.log(f"Changed color of {name} to {hex_color}")

    def import_mesh(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Mesh", "", "3D Files (*.stl *.step *.stp *.obj)"
        )
        if file_path:
            self.log(f"Importing: {os.path.basename(file_path)}")
            import trimesh
            try:
                loaded = trimesh.load(file_path)
                
                # Handle Scenes (often returned by STEP/STEP files)
                if isinstance(loaded, trimesh.Scene):
                    self.log("Detected assembly/scene. Merging meshes...")
                    mesh = loaded.to_mesh() 
                else:
                    mesh = loaded

                # VALIDATION: Check if mesh is empty
                if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
                     self.log("ERROR: Imported mesh has 0 vertices! The file might be empty or incompatible.")
                     return

                # Log mesh stats
                num_v = len(mesh.vertices)
                bounds = mesh.bounds
                size = bounds[1] - bounds[0]
                center = mesh.centroid
                self.log(f"Original Center: {center}")
                
                # NOTE: We do NOT auto-center the mesh geometry anymore.
                # Preserving the original CAD origin is critical for correct joint rotation.

                # Assign a random distinct color
                colors = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6"]
                link_color = random.choice(colors)
                
                name = os.path.basename(file_path).split('.')[0]
                link = self.robot.add_link(name, mesh)
                link.color = link_color
                self.links_list.addItem(name)
                
                # Initially show it at (1, 1, 1) as requested
                t_import = np.eye(4)
                t_import[:3, 3] = [1.0, 1.0, 1.0]
                link.t_offset = t_import
                
                self.canvas.update_link_mesh(name, mesh, t_import, color=link.color)
                self.log(f"Successfully loaded: {name} at (1, 1, 1)")
                
                # Force camera reset
                self.canvas.plotter.render()
                self.canvas.plotter.reset_camera()
                
                self.update_link_colors()
                
            except ImportError as ie:
                self.log(f"MISSING DEPENDENCY: {str(ie)}")
                QtWidgets.QMessageBox.critical(self, "Import Error", 
                    f"To load STEP files, you need extra libraries.\n\nError: {str(ie)}\n\n"
                    "I am currently trying to install 'cascadio' for you. "
                    "Please restart the app once the installation finishes.")
            except Exception as e:
                self.log(f"Error: {str(e)}")
