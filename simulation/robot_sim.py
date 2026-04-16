import pyvista as pv
import numpy as np

# -----------------------------
# Rotation matrices
# -----------------------------
def rot_x(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[1,0,0,0],
                     [0,c,-s,0],
                     [0,s, c,0],
                     [0,0,0,1]])

def rot_y(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[ c,0,s,0],
                     [ 0,1,0,0],
                     [-s,0,c,0],
                     [ 0,0,0,1]])

def rot_z(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c,-s,0,0],
                     [s, c,0,0],
                     [0, 0,1,0],
                     [0, 0,0,1]])

# -----------------------------
# Load meshes (already assembled)
# -----------------------------
base_fixed    = pv.read("simulation/meshes/base_fixed.stl")
base_rot      = pv.read("simulation/meshes/base_rot.stl")
shoulder      = pv.read("simulation/meshes/shoulder.stl")
elbow         = pv.read("simulation/meshes/elbow.stl")
wrist_pitch   = pv.read("simulation/meshes/wrist_pitch.stl")
wrist_roll    = pv.read("simulation/meshes/wrist_roll.stl")
grip_gear     = pv.read("simulation/meshes/gripper_gear.stl")
grip_left     = pv.read("simulation/meshes/gripper_left.stl")
grip_right    = pv.read("simulation/meshes/gripper_right.stl")

# -----------------------------
# Plotter
# -----------------------------
plotter = pv.Plotter()
plotter.set_background("white")

A_base_fix  = plotter.add_mesh(base_fixed, color="lightgray")
A_base_rot  = plotter.add_mesh(base_rot, color="silver")
A_shoulder  = plotter.add_mesh(shoulder, color="lightblue")
A_elbow     = plotter.add_mesh(elbow, color="lightblue")
A_wp        = plotter.add_mesh(wrist_pitch, color="lightgreen")
A_wr        = plotter.add_mesh(wrist_roll, color="khaki")
A_gear      = plotter.add_mesh(grip_gear, color="orange")
A_gl        = plotter.add_mesh(grip_left, color="red")
A_gr        = plotter.add_mesh(grip_right, color="red")

plotter.add_axes()

# -----------------------------
# Joint angles
# -----------------------------
q1=q2=q3=q4=q5=qg=0.0

# -----------------------------
# Update transforms (rotations only)
# -----------------------------
def update():
    global q1,q2,q3,q4,q5,qg

    T1 = rot_z(q1)
    T2 = T1 @ rot_x(q2)
    T3 = T2 @ rot_x(q3)
    T4 = T3 @ rot_x(q4)
    T5 = T4 @ rot_z(q5)

    A_base_rot.user_matrix = T1
    A_shoulder.user_matrix = T2
    A_elbow.user_matrix = T3
    A_wp.user_matrix = T4
    A_wr.user_matrix = T5

    # gripper
    A_gear.user_matrix = T5 @ rot_z(qg)
    A_gl.user_matrix   = T5 @ rot_z(+qg)
    A_gr.user_matrix   = T5 @ rot_z(-qg)

    plotter.render()

# -----------------------------
# Controls
# -----------------------------
def inc(j): 
    def f():
        globals()[j]+=0.05
        update()
    return f

def dec(j):
    def f():
        globals()[j]-=0.05
        update()
    return f

plotter.add_key_event("a", inc("q1"))
plotter.add_key_event("d", dec("q1"))

plotter.add_key_event("w", inc("q2"))
plotter.add_key_event("s", dec("q2"))

plotter.add_key_event("e", inc("q3"))
plotter.add_key_event("q", dec("q3"))

plotter.add_key_event("i", inc("q4"))
plotter.add_key_event("k", dec("q4"))

plotter.add_key_event("j", inc("q5"))
plotter.add_key_event("l", dec("q5"))

plotter.add_key_event("o", inc("qg"))
plotter.add_key_event("p", dec("qg"))

update()
plotter.show()
