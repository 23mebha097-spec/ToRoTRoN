import numpy as np

class Link:
    def __init__(self, name, mesh=None):
        self.name = name
        self.mesh = mesh  # trimesh object
        self.color = "lightgray"
        self.is_base = False
        
        # Local offset matrix from alignment system
        self.t_offset = np.eye(4)
        
        # Current world transform (computed by forward kinematics)
        self.t_world = np.eye(4)
        
        self.parent_joint = None
        self.child_joints = []

class Joint:
    def __init__(self, name, parent_link, child_link, joint_type="revolute"):
        self.name = name
        self.parent_link = parent_link
        self.child_link = child_link
        self.joint_type = joint_type
        
        self.origin = np.array([0.0, 0.0, 0.0]) # Relative to parent link frame
        self.axis = np.array([0.0, 0.0, 1.0])   # Unit vector
        
        self.min_limit = -180.0
        self.max_limit = 180.0
        self.current_value = 0.0
        
        # Link children
        parent_link.child_joints.append(self)
        child_link.parent_joint = self

    def get_matrix(self):
        """
        Returns the transform matrix for this joint.
        Math: T = T(origin) * R(axis, theta) * T(-origin)
        This rotates the frame around the defined 'origin' point.
        """
        theta = np.radians(self.current_value)
        
        # 1. Rotation Matrix (R)
        R = self._rotation_matrix(self.axis, theta)
        
        # 2. Translation Matrices for Pivot (T_origin, T_neg_origin)
        T_o = np.eye(4); T_o[:3, 3] = self.origin
        T_no = np.eye(4); T_no[:3, 3] = -self.origin
        
        # T_pivot = T(o) @ R @ T(-o)
        return T_o @ R @ T_no

    def _rotation_matrix(self, axis, theta):
        # Rodrigues' formula or standard axis-angle
        axis = axis / (np.linalg.norm(axis) + 1e-9)
        a = np.cos(theta / 2.0)
        b, c, d = -axis * np.sin(theta / 2.0)
        aa, bb, cc, dd = a * a, b * b, c * c, d * d
        bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
        return np.array([[aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac), 0],
                         [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab), 0],
                         [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc, 0],
                         [0, 0, 0, 1]])

class Robot:
    def __init__(self):
        self.links = {}
        self.joints = {}
        self.base_link = None

    def add_link(self, name, mesh=None):
        link = Link(name, mesh)
        self.links[name] = link
        return link

    def add_joint(self, name, parent_name, child_name):
        parent = self.links[parent_name]
        child = self.links[child_name]
        
        # --- ROBUSTNESS: A child link can have only one parent joint ---
        if child.parent_joint:
            # Find the name of the existing joint and remove it
            old_joint = child.parent_joint
            # Safe deletion from dictionary while iterating
            names_to_remove = [jn for jn, j in self.joints.items() if j == old_joint]
            for jn in names_to_remove:
                self.remove_joint(jn)
                
        joint = Joint(name, parent, child)
        self.joints[name] = joint
        return joint

    def remove_link(self, name):
        if name not in self.links:
            return
        
        link = self.links[name]
        
        # Cleanup joints
        to_remove_joints = []
        for j_name, joint in self.joints.items():
            if joint.parent_link == link:
                # If removing parent, child stays (bake transform is complex, simplest is keep offset)
                joint.child_link.t_offset = joint.child_link.t_world
                to_remove_joints.append(j_name)
            elif joint.child_link == link:
                to_remove_joints.append(j_name)
        
        for j_name in to_remove_joints:
            joint = self.joints[j_name]
            if joint in joint.parent_link.child_joints:
                joint.parent_link.child_joints.remove(joint)
            joint.child_link.parent_joint = None
            del self.joints[j_name]
            
        del self.links[name]
        
        if self.base_link == link:
            self.base_link = None

    def remove_joint(self, name):
        """Safely removes a joint and clears parent/child references"""
        if name not in self.joints:
            return
            
        joint = self.joints[name]
        parent = joint.parent_link
        child = joint.child_link
        
        # Remove from parent's list of children
        if joint in parent.child_joints:
            parent.child_joints.remove(joint)
            
        # Clear child's reference to parent
        child.parent_joint = None
        
        # Remove from robot's global dict
        del self.joints[name]
        
        # Reset child's world transform to its current relative offset
        # (Usually it remains where it was when joint was deleted)
        self.update_kinematics()

    def update_kinematics(self):
        visited = set()
        
        # 1. Identify Roots
        roots = [l for l in self.links.values() if l.parent_joint is None]
        
        # 2. Prioritize Base
        if self.base_link and self.base_link in roots:
            roots.remove(self.base_link)
            roots.insert(0, self.base_link)

        # 3. Propagate
        for root in roots:
            if root.name in visited: continue
            
            root.t_world = root.t_offset
            visited.add(root.name)
            
            stack = [root]
            while stack:
                parent = stack.pop()
                
                for joint in parent.child_joints:
                    child = joint.child_link
                    if child.name in visited: continue
                    
                    # Compute kinematic transform
                    # Child_World = Parent_World * Joint_Transform * Child_Offset
                    # Joint_Transform = T(p) * R * T(-p) (Rotation about pivot in Parent Frame)
                    # Child_Offset = Static position of child relative to Parent Frame
                    
                    joint_matrix = joint.get_matrix()
                    child.t_world = parent.t_world @ joint_matrix @ child.t_offset
                    
                    visited.add(child.name)
                    stack.append(child)
