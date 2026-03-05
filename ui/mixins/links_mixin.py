from PyQt5 import QtWidgets, QtGui, QtCore
import numpy as np
import os
import random


class LinksMixin:
    """Methods for managing robot links: import, select, base, remove, color."""

    def setup_links_tab(self):
        layout = QtWidgets.QVBoxLayout(self.links_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Section header
        header = QtWidgets.QLabel("COMPONENTS")
        header.setStyleSheet("color: #1976d2; font-size: 16px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(header)
        
        import_btn = QtWidgets.QPushButton("Import STEP / STL")
        import_btn.setCursor(QtCore.Qt.PointingHandCursor)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 12px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        import_btn.clicked.connect(self.import_mesh)
        layout.addWidget(import_btn)
        
        self.links_list = QtWidgets.QListWidget()
        self.links_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 6px 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        self.links_list.itemClicked.connect(self.on_link_selected)
        layout.addWidget(self.links_list)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)
        self.set_base_btn = QtWidgets.QPushButton("Set as Base")
        self.set_base_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.remove_btn = QtWidgets.QPushButton("Remove")
        self.remove_btn.setCursor(QtCore.Qt.PointingHandCursor)
        
        self.set_base_btn.clicked.connect(self.set_as_base)
        self.remove_btn.clicked.connect(self.remove_link)
        
        btn_layout.addWidget(self.set_base_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)


        self.color_btn = QtWidgets.QPushButton("Change Color")
        self.color_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.color_btn.clicked.connect(self.change_color)
        layout.addWidget(self.color_btn)
        
        layout.addStretch()

    def on_link_selected(self, item):
        name = item.text()
        
        # Allow all objects to be selected, including jointed ones
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
        self.refresh_sim_objects_list()

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

    def apply_manual_scale(self):
        """Manually scales the selected link mesh."""
        item = self.links_list.currentItem()
        if not item:
            return
            
        name = item.text()
        if name not in self.robot.links:
            return
            
        scale = self.scale_spin.value()
        if scale == 1.0:
            return
            
        link = self.robot.links[name]
        try:
            link.mesh.apply_scale(scale)
            # Re-apply transform to refresh visual
            self.canvas.update_link_mesh(name, link.mesh, link.t_world, color=link.color)
            self.log(f"Scaled {name} by {scale}x")
            # Reset spinbox
            self.scale_spin.setValue(1.0)
        except Exception as e:
            self.log(f"Scale Error: {e}")

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

                # IMPORT "AS IS" - No forced scale ratios
                bounds = mesh.bounds
                raw_size = bounds[1] - bounds[0]
                max_dim = max(raw_size)
                self.log(f"Original CAD Units: {raw_size[0]:.1f} x {raw_size[1]:.1f} x {raw_size[2]:.1f}")

                # Automatic Unit Detection
                if max_dim < 1.0:
                    self.log(f"Auto-Detected: Unit appears to be METERS ({max_dim:.3f} units). Adjusting graph...")
                    self.canvas.update_grid_scale(0.01)
                elif max_dim > 150:
                    self.log(f"Auto-Detected: Unit appears to be MILLIMETERS ({max_dim:.1f} units). Adjusting graph...")
                    self.canvas.update_grid_scale(10.0)
                
                # Assign a random distinct color
                colors = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6"]
                link_color = random.choice(colors)

                name = os.path.basename(file_path).split('.')[0]
                
                # Handle unique naming
                base_name = name
                counter = 1
                while name in self.robot.links:
                    name = f"{base_name}_{counter}"
                    counter += 1
                
                link = self.robot.add_link(name, mesh)
                link.color = link_color
                
                # Tag as Simulation Object if imported in simulation mode
                if hasattr(self, 'sim_toggle_btn') and self.sim_toggle_btn.isChecked():
                    link.is_sim_obj = True
                
                # Use new helper to add row with 'Eye' button
                self.add_link_item(name)
                
                # Default spawn position: (50, 50, 50) cm
                ratio = self.canvas.grid_units_per_cm
                t_import = np.eye(4)
                t_import[:3, 3] = [50.0 * ratio, 50.0 * ratio, 50.0 * ratio]
                link.t_offset = t_import
                
                self.canvas.update_link_mesh(name, mesh, t_import, color=link.color)
                
                # SELF-ADJUSTING GRAPH: 
                # If component is larger than grid, expand the grid automatically
                actor = self.canvas.actors[name]
                self.canvas.ensure_grid_fits_bounds(actor.GetBounds())
                
                self.log(f"Successfully loaded: {name}")
                
                # Auto-select and focus
                self.canvas.select_actor(name)
                self.canvas.focus_on_actor(name)
                
                self.update_link_colors()
                
                # Refresh Simulation Objects list if needed
                if getattr(link, 'is_sim_obj', False):
                    self.refresh_sim_objects_list()
                
            except ImportError as ie:
                self.log(f"MISSING DEPENDENCY: {str(ie)}")
                QtWidgets.QMessageBox.critical(self, "Import Error", 
                    f"To load STEP files, you need extra libraries.\n\nError: {str(ie)}\n\n"
                    "I am currently trying to install 'cascadio' for you. "
                    "Please restart the app once the installation finishes.")
            except Exception as e:
                self.log(f"Error: {str(e)}")

    def add_link_item(self, name):
        """Helper to add an item to the list with a focus button."""
        item = QtWidgets.QListWidgetItem(self.links_list)
        item.setText(name)
        
        # Create custom widget for the row
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(12, 8, 10, 8)
        
        # Label with Name
        name_label = QtWidgets.QLabel(name)
        name_label.setStyleSheet("border: none; font-size: 16px; font-weight: bold; color: #212121;")
        layout.addWidget(name_label)
        layout.addStretch()
        
        # Focus Button — uses Qt standard icon (always visible on Windows)
        focus_btn = QtWidgets.QPushButton()
        focus_btn.setIcon(widget.style().standardIcon(QtWidgets.QStyle.SP_FileDialogContentsView))
        focus_btn.setIconSize(QtCore.QSize(20, 20))
        focus_btn.setToolTip(f"Focus on {name}")
        focus_btn.setAccessibleName(f"Focus {name}")
        focus_btn.setFixedSize(38, 38)
        focus_btn.setCursor(QtCore.Qt.PointingHandCursor)
        focus_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 19px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: white;
                border-color: #1976d2;
            }
        """)
        focus_btn.clicked.connect(lambda: self.canvas.focus_on_actor(name))
        layout.addWidget(focus_btn)
        
        # Set taller row height
        item.setSizeHint(QtCore.QSize(0, 52))
        
        # Apply to list
        self.links_list.addItem(item)
        self.links_list.setItemWidget(item, widget)
