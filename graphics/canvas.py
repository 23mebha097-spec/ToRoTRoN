import pyvista as pv
from pyvistaqt import QtInteractor
from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
import vtkmodules.vtkRenderingCore as vtkRenderingCore
import vtkmodules.vtkCommonCore as vtkCommonCore

class RobotCanvas(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the pyvista interactor
        self.plotter = QtInteractor(self)
        self.layout.addWidget(self.plotter.interactor)
        
        # Light theme environment
        self.plotter.set_background("white")
        self.plotter.add_axes()
        
        # Bounded grid with simplified labels
        self.plotter.show_bounds(
            xtitle="X", ytitle="Y", ztitle="Z",
            n_xlabels=2, n_ylabels=2, n_zlabels=2,
            fmt="",
            all_edges=True
        )

        # Clean up UI: Removed all bounded boxes and distracting numbers
        try:
            self.plotter.remove_scalar_bar()
        except:
            pass

        # Clean up UI: Removed all bounded boxes and distracting numbers
        try:
            self.plotter.remove_scalar_bar()
        except:
            pass
        
        self.actors = {} # Link name -> actor
        self.selected_name = None
        self.is_dragging = False
        self.last_pos = None
        self.fixed_actors = set() # Set of actor names that cannot be picked or moved
       
        # WE DISABLE PyVista's built-in picking to avoid conflicts
        # Instead, we will use a dedicated vtkCellPicker for surgical precision
        self.cell_picker = vtkRenderingCore.vtkCellPicker()
        self.cell_picker.SetTolerance(0.0005)
        
        # Override interactor events
        self.plotter.interactor.AddObserver("MouseMoveEvent", self._on_mouse_move)
        self.plotter.interactor.AddObserver("LeftButtonPressEvent", self._on_left_down)
        self.plotter.interactor.AddObserver("LeftButtonReleaseEvent", self._on_left_up)

        # Overlay Buttons
        self.focus_btn = QtWidgets.QPushButton("Focus Base", self)
        self.focus_btn.setStyleSheet("background-color: #3d3d3d; color: white; border: 1px solid #555; padding: 5px;")
        self.focus_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.focus_btn.resize(100, 30)

        self.pivot_btn = QtWidgets.QPushButton("🎯 Point", self)
        self.pivot_btn.setStyleSheet("background-color: #3d3d3d; color: white; border: 1px solid #555; padding: 5px;")
        self.pivot_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.pivot_btn.resize(80, 30)
        self.pivot_btn.clicked.connect(self.set_pivot_mode)

        self.on_face_picked_callback = None
        self.on_drop_callback = None
        self.on_deselect_callback = None
        self.picking_face = False
        self.picking_color = "orange"
        self.enable_drag = True
        
        self.interaction_mode = "rotate" # 'rotate', 'pivot'

        # Keyboard Shortcut: Escape to deselect everything
        self.plotter.add_key_event("Escape", self.deselect_all)

    def _dist_point_to_segment(self, p, a, b):
        """Calculates distance from point p to line segment (a, b)"""
        pa = p - a
        ba = b - a
        denom = np.dot(ba, ba)
        if denom < 1e-18: return np.linalg.norm(pa)
        h = np.clip(np.dot(pa, ba) / denom, 0, 1)
        return np.linalg.norm(pa - ba * h)

    def _on_face_pick_click(self, click_pos):
        """Enhanced face picking - detects geometric features and picks specific loops."""
        self.cell_picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
        cell_id = self.cell_picker.GetCellId()
        actor = self.cell_picker.GetActor()

        if cell_id != -1 and actor:
            link_name = next((name for name, a in self.actors.items() if a == actor), None)
            
            if link_name:
                mesh = pv.wrap(actor.GetMapper().GetInput())
                
                # 1. Get seed face normal
                seed_normal = self._get_face_normal(mesh, cell_id)
                
                # 2. Grow region of coplanar/co-cylindrical faces
                feature_cells = self._grow_feature_region(mesh, cell_id, seed_normal)
                
                # 3. Find ALL loops on this feature (e.g. outer boundary and holes)
                loops = self._extract_boundary_edges(mesh, feature_cells)
                
                if not loops:
                    return False
                
                # 4. Find the loop closest to the user's click
                mat = actor.user_matrix
                inv_mat = np.linalg.inv(mat)
                world_pick_pt = self.cell_picker.GetPickPosition()
                local_pick_pt = (inv_mat @ np.append(world_pick_pt, 1))[:3]
                
                best_loop = None
                min_dist = float('inf')
                
                for loop in loops:
                    for edge in loop:
                        p1 = np.array(mesh.GetPoint(edge[0]))
                        p2 = np.array(mesh.GetPoint(edge[1]))
                        d = self._dist_point_to_segment(local_pick_pt, p1, p2)
                        if d < min_dist:
                            min_dist = d
                            best_loop = loop
                
                if best_loop:
                    # 5. Calculate center and normal for JUST this loop
                    center, normal = self._calc_loop_center_normal(mesh, best_loop, seed_normal)
                    
                    rot = mat[:3, :3]
                    world_normal = rot @ normal
                    world_center = (mat @ np.append(center, 1))[:3]
                    
                    if self.on_face_picked_callback:
                        self.on_face_picked_callback(link_name, world_center, world_normal)
                    
                    # 6. Visual Highlight - show ONLY the selected boundary loop
                    self._highlight_feature_boundary(mesh, best_loop, link_name, mat)
                
                self.picking_face = False
                self.plotter.render()
                return True
        return False

    def _get_face_normal(self, mesh, cell_id):
        """Get normal vector of a face"""
        cell = mesh.GetCell(cell_id)
        points = cell.GetPoints()
        pts = np.array([points.GetPoint(i) for i in range(points.GetNumberOfPoints())])
        
        if len(pts) >= 3:
            v1 = pts[1] - pts[0]
            v2 = pts[2] - pts[0]
            normal = np.cross(v1, v2)
            norm = np.linalg.norm(normal)
            return normal / norm if norm > 0 else np.array([0,0,1])
        return np.array([0,0,1])

    def _grow_feature_region(self, mesh, seed_id, seed_normal, angle_tol=10.0):
        """Grow region of faces with similar normals - properly finds all neighbors"""
        # Build connectivity for neighbor finding
        mesh.BuildLinks()
        
        visited = set()
        to_visit = [seed_id]
        feature = []
        
        cos_tol = np.cos(np.radians(angle_tol))
        
        while to_visit and len(feature) < 1000:  # Increased limit for circular features
            current = to_visit.pop(0)  # Use queue (FIFO) for better growth pattern
            if current in visited or current < 0 or current >= mesh.GetNumberOfCells():
                continue
                
            visited.add(current)
            current_normal = self._get_face_normal(mesh, current)
            
            # Check if normal is similar (coplanar/co-cylindrical check)
            similarity = abs(np.dot(current_normal, seed_normal))
            if similarity >= cos_tol:
                feature.append(current)
                
                # Find all adjacent cells through shared edges
                cell = mesh.GetCell(current)
                n_edges = cell.GetNumberOfEdges()
                
                for i in range(n_edges):
                    edge = cell.GetEdge(i)
                    # Get the two point IDs of this edge
                    p1 = edge.GetPointId(0)
                    p2 = edge.GetPointId(1)
                    
                    # Find cells that share this edge
                    id_list = vtkCommonCore.vtkIdList()
                    mesh.GetCellEdgeNeighbors(current, p1, p2, id_list)
                    
                    for j in range(id_list.GetNumberOfIds()):
                        neighbor_id = id_list.GetId(j)
                        if neighbor_id not in visited:
                            to_visit.append(neighbor_id)
                    
        return feature if feature else [seed_id]

    def _extract_boundary_edges(self, mesh, cell_ids):
        """Extract boundary edges and return them as a list of independent continuous loops"""
        edge_count = {}
        for cid in cell_ids:
            cell = mesh.GetCell(cid)
            n_pts = cell.GetNumberOfPoints()
            for i in range(n_pts):
                p1 = cell.GetPointId(i)
                p2 = cell.GetPointId((i + 1) % n_pts)
                edge = tuple(sorted([p1, p2]))
                edge_count[edge] = edge_count.get(edge, 0) + 1
        
        # Boundary edges appear only once in the set of faces
        boundary = [e for e, count in edge_count.items() if count == 1]
        
        if not boundary:
            return []
            
        return self._sort_edges_into_loops(boundary)

    def _sort_edges_into_loops(self, edges):
        """Sort disconnected edges into separate continuous boundary loops"""
        if not edges:
            return []
            
        point_to_edges = {}
        for edge in edges:
            for pt in edge:
                if pt not in point_to_edges:
                    point_to_edges[pt] = []
                point_to_edges[pt].append(edge)
        
        all_loops = []
        remaining = set(edges)
        
        while remaining:
            loop = []
            current_edge = remaining.pop()
            loop.append(current_edge)
            
            # Trace from the current end point
            current_end = current_edge[1]
            
            while True:
                next_edge = None
                for candidate in point_to_edges.get(current_end, []):
                    if candidate in remaining:
                        next_edge = candidate
                        break
                
                if next_edge is None:
                    break
                    
                # Orient edge correctly to maintain flow
                if next_edge[0] == current_end:
                    loop.append(next_edge)
                    current_end = next_edge[1]
                else:
                    loop.append((next_edge[1], next_edge[0]))
                    current_end = next_edge[0]
                    
                remaining.discard(next_edge)
            all_loops.append(loop)
            
        return all_loops

    def _calc_loop_center_normal(self, mesh, loop, seed_normal):
        """Calculate centroid of a boundary loop and return with seed normal"""
        all_pts = []
        for edge in loop:
            all_pts.append(np.array(mesh.GetPoint(edge[0])))
        
        if all_pts:
            center = np.mean(all_pts, axis=0)
        else:
            center = np.zeros(3)
        
        return center, seed_normal

    def _highlight_feature_boundary(self, mesh, boundary_edges, link_name, matrix):
        """Create visual highlight for feature boundary"""
        if not boundary_edges:
            return
            
        # Create line segments for boundary
        points = []
        lines = []
        point_map = {}
        
        for edge in boundary_edges:
            # Get or create points
            if edge[0] not in point_map:
                point_map[edge[0]] = len(points)
                points.append(mesh.GetPoint(edge[0]))
            if edge[1] not in point_map:
                point_map[edge[1]] = len(points)
                points.append(mesh.GetPoint(edge[1]))
            
            # Add line: [num_points, idx1, idx2]
            lines.extend([2, point_map[edge[0]], point_map[edge[1]]])
        
        if points and lines:
            boundary_mesh = pv.PolyData(points)
            boundary_mesh.lines = np.array(lines)
            
            highlight_name = f"pick_highlight_{link_name}"
            self.plotter.add_mesh(boundary_mesh, color="blue", line_width=5,
                                name=highlight_name, user_matrix=matrix, pickable=False)

    def clear_highlights(self):
        """Removes all temporary selection markers (faces, arrows) from the scene."""
        current_actors = list(self.plotter.renderer.actors.keys())
        for actor_name in current_actors:
            if "pick_highlight_" in actor_name or "pick_arrow_" in actor_name:
                self.plotter.remove_actor(actor_name)
        self.plotter.render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Top right corner, with some margin
        self.focus_btn.move(self.width() - 110, 10)
        self.pivot_btn.move(self.width() - 200, 10) # Position to left of Focus btn

    def set_pivot_mode(self):
        self.interaction_mode = "pivot"
        self.pivot_set = False # Reset state so we can pick a new point
        self.pivot_btn.setStyleSheet("background-color: #4CAF50; color: white; border: 1px solid #555; padding: 5px;") # Green active
        self.mw_log("Mode: Pivot Point. Click ONCE to set, then rotate.")

    def mw_log(self, msg):
        # Helper to log back to main window if possible
        if hasattr(self.parent(), 'log'):
            self.parent().log(msg)
        elif hasattr(self.window(), 'log'):
            self.window().log(msg)

    def deselect_all(self):
        """Standard CAD behavior: Escape or blank click clears everything."""
        
        # 1. PRIORITY: If in Pivot Mode, just exit that mode and return
        if self.interaction_mode == "pivot":
            self.interaction_mode = "rotate"
            self.pivot_set = False
            self.pivot_btn.setStyleSheet("background-color: #3d3d3d; color: white; border: 1px solid #555; padding: 5px;")
            self.plotter.remove_actor("pivot_marker")
            self.mw_log("Exited Pivot Mode.")
            self.plotter.render()
            return # <--- EXIT HERE, don't clear selection

        # 2. Standard Deselect (only if NOT in pivot mode)
        self.selected_name = None
        self.is_dragging = False
        self.picking_face = False
        self.pivot_set = False 
        
        # Reset visual highlights (Edge Colors)
        for actor in self.actors.values():
            actor.GetProperty().SetEdgeColor([0.5, 0.5, 0.5])
            
        # Clear alignment highlights if any
        self.clear_highlights()
        
        if self.on_deselect_callback:
            self.on_deselect_callback()
            
        self.mw_log("Selection cleared.")
        self.plotter.render()

    def start_face_picking(self, callback, color="orange"):
        """Activates specialized face picking mode."""
        self.on_face_picked_callback = callback
        self.picking_face = True
        self.picking_color = color
        self.mw_log(f"Face Picking Active: Click a face on the 3D model...")

    # ... [Existing events remain unchanged] ...

    def focus_on_bounds(self, bounds):
        """Resets camera to fit the specified bounds."""
        self.plotter.reset_camera(bounds=bounds)
        self.plotter.render()

    def start_object_picking(self, callback, label="Object"):
        """Activates silent object picking - returns name without highlighting"""
        self.on_object_picked_callback = callback
        self.picking_object = True
        self.picking_label = label
        self.mw_log(f"Click a 3D object to select it as {label}...")
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def start_object_picking_double(self, callback, label="Object"):
        """Activates double-click object picking - returns name without highlighting"""
        self.on_object_picked_callback = callback
        self.picking_object_double = True
        self.picking_label = label
        self.mw_log(f"Double-click a 3D object to select it as {label}...")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        
        # Add double-click observer if not already added
        if not hasattr(self, '_double_click_observer_added'):
            self.plotter.interactor.AddObserver("LeftButtonDoubleClickEvent", self._on_double_click)
            self._double_click_observer_added = True

    def _on_double_click(self, obj, event):
        """Handle double-click event for object selection"""
        if not hasattr(self, 'picking_object_double') or not self.picking_object_double:
            return
        
        self.mw_log("Double-click detected!")  # Debug
        
        click_pos = self.plotter.interactor.GetEventPosition()
        self.plotter.picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
        actor = self.plotter.picker.GetActor()
        
        if actor:
            # Find the name of the clicked actor
            for name, a in self.actors.items():
                if a == actor:
                    if self.on_object_picked_callback:
                        self.on_object_picked_callback(name)
                    self.mw_log(f"{self.picking_label} selected: {name}")
                    break
        else:
            self.mw_log("No object under cursor")
        
        # Reset state
        self.picking_object_double = False
        self.on_object_picked_callback = None
        self.setCursor(QtCore.Qt.ArrowCursor)

    def cancel_object_picking(self):
        """Cancel active object picking mode without callback"""
        self.picking_object = False
        self.picking_object_double = False
        self.on_object_picked_callback = None
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.mw_log("Selection cancelled.")

    def start_point_picking(self, callback):
        """Activates point picking mode for Joint Origin selection."""
        self.on_point_picked_callback = callback
        self.picking_point = True
        self.mw_log("Pick a point in 3D space for the Joint Pivot...")
        self.setCursor(QtCore.Qt.CrossCursor)

    def _on_left_down(self, obj, event):
        click_pos = self.plotter.interactor.GetEventPosition()
        
        # --- DOUBLE-CLICK DETECTION (CUSTOM) ---
        if hasattr(self, 'picking_object_double') and self.picking_object_double:
            import time
            current_time = time.time()
            
            # Pick the actor
            self.plotter.picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
            actor = self.plotter.picker.GetActor()
            
            # Check if this is a double-click (within 300ms of last click on same actor)
            if hasattr(self, '_last_click_time') and hasattr(self, '_last_click_actor'):
                time_diff = current_time - self._last_click_time
                if time_diff < 0.3 and actor == self._last_click_actor and actor is not None:
                    # DOUBLE-CLICK DETECTED!
                    self.mw_log("Double-click detected!")
                    
                    # Find the name of the clicked actor
                    for name, a in self.actors.items():
                        if a == actor:
                            if self.on_object_picked_callback:
                                self.on_object_picked_callback(name)
                            self.mw_log(f"{self.picking_label} selected: {name}")
                            break
                    
                    # Reset state
                    self.picking_object_double = False
                    self.on_object_picked_callback = None
                    self.setCursor(QtCore.Qt.ArrowCursor)
                    self._last_click_time = None
                    self._last_click_actor = None
                    return
            
            # Store this click for double-click detection
            self._last_click_time = current_time
            self._last_click_actor = actor
            return
        
        # --- OBJECT PICKING MODE (JOINT PARENT/CHILD) ---
        if hasattr(self, 'picking_object') and self.picking_object:
            self.plotter.picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
            actor = self.plotter.picker.GetActor()
            
            if actor:
                # Find the name of the clicked actor
                for name, a in self.actors.items():
                    if a == actor:
                        if self.on_object_picked_callback:
                            self.on_object_picked_callback(name)
                        self.mw_log(f"{self.picking_label} selected: {name}")
                        break
            
            # Reset state
            self.picking_object = False
            self.on_object_picked_callback = None
            self.setCursor(QtCore.Qt.ArrowCursor)
            return
        
        # --- POINT PICKING MODE (JOINT ORIGIN) ---
        if hasattr(self, 'picking_point') and self.picking_point:
            self.plotter.picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
            picked_pos = self.plotter.picker.GetPickPosition()
            
            # Use picked position (even if on grid/empty space, though usually on object)
            if self.on_point_picked_callback:
                self.on_point_picked_callback(picked_pos)
            
            # Reset state
            self.picking_point = False
            self.on_point_picked_callback = None
            self.setCursor(QtCore.Qt.ArrowCursor)
            self.mw_log(f"Point picked: {np.round(picked_pos, 2)}")
            return # Block other interactions

        if self.interaction_mode == "pivot":
            # ONE-SHOT LOGIC: If pivot is already set, just rotate around it.
            if self.pivot_set:
                self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()
                return

            # 1. Pick the point under cursor
            self.plotter.picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
            picked_pos = self.plotter.picker.GetPickPosition()
            
            # 2. Set Focal Point (Pivot)
            self.plotter.camera.focal_point = picked_pos
            
            # 3. Show Feedback (Tiny Sphere)
            self.plotter.remove_actor("pivot_marker")
            sphere = pv.Sphere(radius=0.05, center=picked_pos) 
            self.plotter.add_mesh(sphere, color="red", name="pivot_marker", pickable=False)
            
            self.pivot_set = True # LOCK the pivot
            self.mw_log(f"Pivot LOCKED at: {np.round(picked_pos, 2)}. Press Esc to reset.")
            
            # 4. Delegate to default Interactor Style (Rotate)
            self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()
                
            return
        
        # CASE 0: FACE PICKING IN PROGRESS
        if self.picking_face:
            if self._on_face_pick_click(click_pos):
                return # Successfully picked face, block everything else
            else:
                self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()
                return
        
        # Check if we hit an actor
        self.plotter.picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
        actor = self.plotter.picker.GetActor()

        # CASE 1: We are already dragging something
        if self.is_dragging:
            # A left click while dragging confirms placement (drops it)
            if self.selected_name and self.on_drop_callback:
                mat = self.actors[self.selected_name].user_matrix
                self.on_drop_callback(self.selected_name, mat)

            self.is_dragging = False
            self.selected_name = None
            for a in self.actors.values():
                a.GetProperty().SetEdgeColor([0.5, 0.5, 0.5]) # Reset highlights
            
            # Allow camera interaction immediately after drop
            self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()
            return

        # CASE 2: We clicked on an object (START DRAGGING)
        if actor:
            # CHECK: Interaction Mode (Disable drag in Align/Joint tabs)
            if not self.enable_drag:
                # Still allow selection for UI sync, but don't start dragging
                for name, a in self.actors.items():
                    if a == actor:
                        self.select_actor(name)
                        break
                self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()
                return
            
            # Identify the clicked link
            clicked_name = None
            for name, a in self.actors.items():
                if a == actor:
                    clicked_name = name
                    break
            
            # --- ENGINEERING CONSTRAINT: LOCKED/ALIGNED COMPONENTS ---
            # If a link has a parent joint (i.e., it is aligned/attached to something),
            # it should NOT be moveable by the free-drag tool. It is "Constrained".
            # We access the Robot model via MainWindow to check this.
            if hasattr(self.window(), 'robot') and clicked_name:
                robot = self.window().robot
                if clicked_name in robot.links:
                    link = robot.links[clicked_name]
                    if link.parent_joint:
                        self.mw_log(f"\u26a0 Locked: '{clicked_name}' is aligned/jointed. Unjoint reset transform to move freely.")
                        self.select_actor(clicked_name) # Select it visually
                        self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown() # Allow camera rotate
                        return

            # CHECK: Is this the Base Link? (Bases are fixed/non-pickable for dragging)
            if clicked_name in self.fixed_actors:
                # Just let the camera rotate, don't select or drag
                self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()
                return
            
            # If we clicked the base, IGNORE it (don't start dragging)
            # We assume the user has access to MainWindow.robot.base_link
            # But here we can just check if it's the first imported object or marked as base
            # For robustness, we will let MainWindow handle the 'Base' logic 
            # and just check a 'fixed' property on actors if we want, 
            # but for now, we'll implement the 'not selectable' logic in MainWindow.
            
            self.is_dragging = True
            self.last_pos = click_pos
            
            # Find and select the clicked link
            found = False
            for name, a in self.actors.items():
                if a == actor:
                    self.selected_name = name
                    a.GetProperty().SetEdgeColor([1, 1, 0]) # Yellow focus
                    found = True
                else:
                    a.GetProperty().SetEdgeColor([0.5, 0.5, 0.5]) # Gray out others
            
            if found:
                return # Stop event here (don't rotate camera)

        # CASE 3: We clicked on empty space
        # Just rotate the camera, do NOT select anything
        self.plotter.interactor.GetInteractorStyle().OnLeftButtonDown()

    def _on_left_up(self, obj, event):
        # Pass through to default interactor to finish camera rotation
        self.plotter.interactor.GetInteractorStyle().OnLeftButtonUp()
        
    def _on_right_down(self, obj, event):
        # Right click to CANCEL / DROP selection
        if self.is_dragging:
            # SYNC: Save final position before dropping
            if self.selected_name and self.on_drop_callback:
                mat = self.actors[self.selected_name].user_matrix
                self.on_drop_callback(self.selected_name, mat)

            self.is_dragging = False
            self.selected_name = None
            # Reset colors
            for a in self.actors.values():
                a.GetProperty().SetEdgeColor([0.5, 0.5, 0.5])
            return # Consume event
            
        # Otherwise, let default right-click behavior happen (usually zoom)
        self.plotter.interactor.GetInteractorStyle().OnRightButtonDown()

    def _on_mouse_move(self, obj, event):
        if self.is_dragging and self.selected_name:
            curr_pos = self.plotter.interactor.GetEventPosition()
            if self.last_pos:
                # Calculate mouse delta in pixels
                dx = curr_pos[0] - self.last_pos[0]
                dy = curr_pos[1] - self.last_pos[1]
                
                actor = self.actors[self.selected_name]
                camera = self.plotter.camera
                
                # Get exact camera and window properties
                window_size = self.plotter.render_window.GetSize()
                view_angle = np.radians(camera.GetViewAngle())
                
                # Distance from camera to object
                dist = np.linalg.norm(np.array(camera.GetPosition()) - np.array(actor.GetCenter()))
                
                # Pixel-to-World scaling: 
                # At distance 'dist', the screen height in world units is 2 * dist * tan(FOV/2)
                world_height = 2.0 * dist * np.tan(view_angle / 2.0)
                scale = world_height / window_size[1] # Scale based on vertical pixels
                
                # View-plane basis vectors
                view_up = np.array(camera.GetViewUp())
                view_up /= (np.linalg.norm(view_up) + 1e-6)
                view_dir = np.array(camera.GetDirectionOfProjection())
                side = np.cross(view_dir, view_up)
                side /= (np.linalg.norm(side) + 1e-6)
                
                # Translate the part
                move_vector = (side * dx + view_up * dy) * scale
                
                mat = actor.user_matrix
                mat[0, 3] += move_vector[0]
                mat[1, 3] += move_vector[1]
                mat[2, 3] += move_vector[2]
                actor.user_matrix = mat
                
                self.last_pos = curr_pos
                self.plotter.render()
            return 
            
        self.plotter.interactor.GetInteractorStyle().OnMouseMove()
    def update_link_mesh(self, link_name, mesh, transform, color="silver"):
        """Adds or updates a link mesh in the scene."""
        if link_name in self.actors:
            self.plotter.remove_actor(self.actors[link_name])
        
        # Convert trimesh to pyvista if needed
        import trimesh
        if isinstance(mesh, trimesh.Trimesh):
            poly = pv.wrap(mesh)
        else:
            poly = mesh # assume it's already pyvista compatible
            
        # Use provided color instead of hardcoded silver
        actor = self.plotter.add_mesh(poly, color=color, show_edges=True, name=link_name)
        # Apply transform
        actor.user_matrix = transform
        self.actors[link_name] = actor
        self.plotter.render()

    def set_actor_color(self, name, hex_color):
        """Changes the color of an existing actor."""
        if name in self.actors:
            self.actors[name].GetProperty().SetColor(QtGui.QColor(hex_color).getRgbF()[:3])
            self.plotter.render()

    def select_actor(self, name):
        """Programmatically select and highlight an actor by name."""
        if name not in self.actors:
            return
        
        self.selected_name = name
        # Highlight
        for n, actor in self.actors.items():
            if n == name:
                actor.GetProperty().SetEdgeColor([1, 1, 0]) # Yellow
            else:
                actor.GetProperty().SetEdgeColor([0.5, 0.5, 0.5]) # Gray
        self.plotter.render()

    def remove_actor(self, name):
        """Removes an actor from the scene by name."""
        if name in self.actors:
            self.plotter.remove_actor(self.actors[name])
            del self.actors[name]
            
            # If the removed actor was selected, clear selection
            if self.selected_name == name:
                self.selected_name = None
                self.is_dragging = False
                
            self.plotter.render()

    def update_transforms(self, robot):
        """Updates all actor transforms based on robot's current kinematics state."""
        for name, link in robot.links.items():
            if name in self.actors:
                self.actors[name].user_matrix = link.t_world
        self.plotter.render()


    # ── JOINT MOTION TRAIL (Ghost Shadows) ──────────────────────────────────
    def _init_ghost_system(self):
        """Initialize ghost trail tracking (called lazily on first use)."""
        if not hasattr(self, '_ghost_data'):
            self._ghost_data = {}  # name -> {'actor': actor, 'time': start_time}
            self._ghost_counter = 0
            self._fade_timer = QtCore.QTimer(self)
            self._fade_timer.timeout.connect(self._process_ghost_fading)
            self._fade_timer.start(500) # Update every 500ms

    def add_joint_ghost(self, mesh, transform, color="#888888", opacity=0.1):
        """
        Adds one semi-transparent ghost snapshot of a link at its current
        transform. Resets the 10-second auto-clear timer on every call.

        Parameters:
            mesh      : trimesh or pyvista mesh of the link
            transform : 4x4 world transform numpy array
            color     : hex or named color — ideally the link's own color
            opacity   : transparency level (0=invisible, 1=solid)
        """
        self._init_ghost_system()

        try:
            import pyvista as _pv
            import trimesh as _trimesh
            import time as _time

            # Convert if trimesh
            if isinstance(mesh, _trimesh.Trimesh):
                poly = _pv.wrap(mesh)
            else:
                poly = mesh

            # Cap ghost count at 5000 for maximum persistence
            if len(self._ghost_data) >= 5000:
                oldest_key = next(iter(self._ghost_data))
                try:
                    self.plotter.remove_actor(self._ghost_data[oldest_key]['actor'])
                except Exception:
                    pass
                del self._ghost_data[oldest_key]

            # Add to scene
            ghost_name = f"_ghost_{self._ghost_counter}"
            self._ghost_counter += 1

            actor = self.plotter.add_mesh(
                poly,
                color=color,
                opacity=opacity,
                show_edges=False,
                name=ghost_name,
                pickable=False,
                user_matrix=transform,
                lighting=False, # Flat color for "clearer" light look
            )
            
            self._ghost_data[ghost_name] = {
                'actor': actor,
                'start_time': _time.time(),
                'init_opacity': opacity
            }

        except Exception:
            pass

    def _process_ghost_fading(self):
        """Removes ghosts only after 101s. Shadows do not vanish during simulation."""
        import time as _time
        now = _time.time()
        
        # Check if any simulation is currently running
        is_running = False
        try:
            if hasattr(self.window(), 'program_tab'):
                is_running = self.window().program_tab.is_running
        except:
            pass

        to_remove = []
        for name, data in self._ghost_data.items():
            if is_running:
                # Refresh start_time while active so they never expire mid-sim
                data['start_time'] = now 
                continue
                
            age = now - data['start_time']
            if age >= 101.0:
                to_remove.append(name)
            # Static opacity, no fade calculation as per request
        
        if to_remove:
            for name in to_remove:
                try:
                    self.plotter.remove_actor(self._ghost_data[name]['actor'])
                except Exception:
                    pass
                del self._ghost_data[name]
                
        if self._ghost_data or to_remove:
            try:
                self.plotter.render()
            except:
                pass

    def clear_joint_ghosts(self):
        """Removes all ghost shadow actors from the scene."""
        if not hasattr(self, '_ghost_data'): return
        for name in list(self._ghost_data.keys()):
            try:
                self.plotter.remove_actor(self._ghost_data[name]['actor'])
            except:
                pass
        self._ghost_data.clear()
        self.plotter.render()

    def clear_rotation_discs(self):
        """Removes rotation disc overlays from the scene."""
        pass
