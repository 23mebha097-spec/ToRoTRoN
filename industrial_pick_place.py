# -*- coding: utf-8 -*-
"""
industrial_pick_place.py
========================
6-DOF Industrial Pick-and-Place Controller
  - Orientation-locked gripper (object RPY preserved from pick to place)
  - Quadrant-aware radial transfer routing
      * Diagonal quadrant crossings (e.g. Q++ -> Q--) are split into:
          Leg-1: rotate base joint to nearest intermediate quadrant
          Leg-2: full IK move to final destination
  - Damped Least Squares numerical IK with random restarts
"""

import sys
import numpy as np
import logging

# Force UTF-8 output so Unicode chars in logs render correctly on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RobotController")


# ==============================================================================
#  RobotArm
# ==============================================================================
class RobotArm:
    def __init__(self):
        # 6-DOF DH Parameters  [alpha, a, d, theta_offset]  (UR5-like)
        self.dh_params = [
            ( np.pi/2,  0.0,      0.1625, 0.0),
            ( 0.0,     -0.425,    0.0,    0.0),
            ( 0.0,     -0.39225,  0.0,    0.0),
            ( np.pi/2,  0.0,      0.1333, 0.0),
            (-np.pi/2,  0.0,      0.0997, 0.0),
            ( 0.0,      0.0,      0.0996, 0.0),
        ]
        self.joint_limits  = [(-2*np.pi, 2*np.pi)] * 6
        self.current_joints = np.array([0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0])
        self.home_position  = self.current_joints.copy()

    # ------------------------------------------------------------------
    def forward_kinematics(self, joints):
        """Standard DH forward kinematics -> 4x4 pose matrix."""
        T = np.eye(4)
        for i in range(6):
            alpha, a, d, offset = self.dh_params[i]
            theta = joints[i] + offset
            Ti = np.array([
                [np.cos(theta), -np.sin(theta)*np.cos(alpha),  np.sin(theta)*np.sin(alpha), a*np.cos(theta)],
                [np.sin(theta),  np.cos(theta)*np.cos(alpha), -np.cos(theta)*np.sin(alpha), a*np.sin(theta)],
                [0,              np.sin(alpha),                 np.cos(alpha),               d              ],
                [0,              0,                             0,                           1              ],
            ])
            T = T @ Ti
        return T

    # ------------------------------------------------------------------
    def _ik_attempt(self, target_pose, q_start, max_iter, tol, damping):
        """Single Damped-Least-Squares IK attempt from q_start."""
        q = q_start.copy()
        for i in range(max_iter):
            T    = self.forward_kinematics(q)
            p_err = target_pose[:3, 3] - T[:3, 3]

            R_err = target_pose[:3, :3] @ T[:3, :3].T
            vec   = np.array([R_err[2,1]-R_err[1,2],
                               R_err[0,2]-R_err[2,0],
                               R_err[1,0]-R_err[0,1]])
            sin_a = np.linalg.norm(vec) / 2.0
            cos_a = np.clip((np.trace(R_err) - 1) / 2.0, -1.0, 1.0)
            angle = np.arctan2(sin_a, cos_a)
            r_err = (vec / (2*sin_a)) * angle if sin_a > 1e-7 else np.zeros(3)

            err      = np.hstack((p_err, r_err))
            err_norm = np.linalg.norm(err)
            if err_norm < tol:
                return q, err_norm

            J    = self._compute_jacobian(q)
            step = 0.5 if i < max_iter // 2 else 0.2
            dq   = J.T @ np.linalg.solve(J @ J.T + damping**2 * np.eye(6), err)
            q   += dq * step

        return None, float("inf")

    def inverse_kinematics(self, target_pose, num_restarts=6):
        """DLS IK with warm start then random restarts."""
        tol     = 1e-3
        damping = 0.05
        iters   = 300

        q, _ = self._ik_attempt(target_pose, self.current_joints, iters, tol, damping)
        if q is not None:
            return q, "Success"

        np.random.seed(42)
        for _ in range(num_restarts):
            q_rand = np.random.uniform(-np.pi, np.pi, 6)
            q, _   = self._ik_attempt(target_pose, q_rand, iters, tol, damping)
            if q is not None:
                if all(lo <= q[j] <= hi for j, (lo, hi) in enumerate(self.joint_limits)):
                    return q, "Success (restart)"

        return None, f"IK failed after {num_restarts} restarts"

    # ------------------------------------------------------------------
    def _compute_jacobian(self, q):
        """Compute 6x6 geometric Jacobian."""
        J = np.zeros((6, 6))
        T = np.eye(4)
        origins = [T[:3, 3].copy()]
        z_axes  = [T[:3, 2].copy()]

        for i in range(6):
            alpha, a, d, offset = self.dh_params[i]
            theta = q[i] + offset
            Ti = np.array([
                [np.cos(theta), -np.sin(theta)*np.cos(alpha),  np.sin(theta)*np.sin(alpha), a*np.cos(theta)],
                [np.sin(theta),  np.cos(theta)*np.cos(alpha), -np.cos(theta)*np.sin(alpha), a*np.sin(theta)],
                [0,              np.sin(alpha),                 np.cos(alpha),               d              ],
                [0,              0,                             0,                           1              ],
            ])
            T = T @ Ti
            origins.append(T[:3, 3].copy())
            z_axes.append(T[:3, 2].copy())

        p_n = origins[-1]
        for i in range(6):
            J[:3, i] = np.cross(z_axes[i], p_n - origins[i])
            J[3:, i] = z_axes[i]
        return J


# ==============================================================================
#  Gripper
# ==============================================================================
class Gripper:
    def __init__(self, gtype="parallel"):
        self.gtype   = gtype
        self.is_open = True

    def toggle(self, state):
        self.is_open = (state == "open")
        logger.info("[GRIPPER] %s confirmed", state.upper())
        return True


# ==============================================================================
#  MotionPlanner
# ==============================================================================
class MotionPlanner:
    def __init__(self, robot):
        self.robot = robot

    def plan(self, start_q, end_q, steps=20):
        """Cubic-smoothed joint-space trajectory."""
        traj = []
        for i in range(steps):
            t = i / (steps - 1)
            s = 3*t**2 - 2*t**3          # smooth-step
            traj.append(start_q + (end_q - start_q) * s)
        return traj

    @staticmethod
    def rpy_to_matrix(r, p, yaw):
        """ZYX Euler angles -> 3x3 rotation matrix."""
        cr, sr = np.cos(r),   np.sin(r)
        cp, sp = np.cos(p),   np.sin(p)
        cy, sy = np.cos(yaw), np.sin(yaw)
        return np.array([
            [cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr],
            [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr],
            [-sp,    cp*sr,            cp*cr           ],
        ])

    @staticmethod
    def get_pose_locked(x, y, z, R_fixed):
        """4x4 pose with a FIXED (locked) rotation matrix."""
        T = np.eye(4)
        T[:3, :3] = R_fixed
        T[:3, 3]  = [x, y, z]
        return T


# ==============================================================================
#  QuadrantRouter  --  Radial-first transfer planner
# ==============================================================================
class QuadrantRouter:
    """
    Quadrant-Aware Transfer Router
    ===============================
    Quadrants of the XY workspace (viewed from above):
        Q++  x>=0, y>=0
        Q+-  x>=0, y<0
        Q-+  x<0,  y>=0
        Q--  x<0,  y<0

    Strategy for a diagonal cross (e.g. Q++ -> Q--):
    -------------------------------------------------
    Instead of moving all joints simultaneously diagonally, we:

      Leg 1  Rotate base joint (J0) to the NEAREST intermediate quadrant.
             Two candidates exist:
               Cand-A  (place_x, pick_y)  -- change X first (keeps Y of pick)
               Cand-B  (pick_x,  place_y) -- change Y first (keeps X of pick)
             The nearer one (Euclidean from pick XY) is chosen.

      Leg 2  Full IK move to the final place position.

    For a single-axis cross or same quadrant, a direct move is used.
    """

    @staticmethod
    def _quad(x, y):
        return (1 if x >= 0 else -1, 1 if y >= 0 else -1)

    @staticmethod
    def _quad_str(sx, sy):
        return "Q" + ("+" if sx > 0 else "-") + ("+" if sy > 0 else "-")

    @staticmethod
    def _dist2d(a, b):
        return np.hypot(a[0]-b[0], a[1]-b[1])

    @classmethod
    def get_transfer_waypoints(cls, pick_xy, place_xy, z_safe):
        """
        Returns
        -------
        (waypoints, route_desc)
          waypoints  : [(x, y, z, label), ...]
          route_desc : human-readable routing summary
        """
        px, py = pick_xy
        dx, dy = place_xy

        qp  = cls._quad(px, py)
        qd  = cls._quad(dx, dy)
        wps = []

        x_cross = (qp[0] != qd[0])
        y_cross = (qp[1] != qd[1])

        if x_cross and y_cross:
            # ---  Diagonal quadrant cross  -----------------------------------
            cand_A = (dx, py)          # share pick-Y, use dest-X  (change X first)
            cand_B = (px, dy)          # share pick-X, use dest-Y  (change Y first)

            if cls._dist2d((px, py), cand_A) <= cls._dist2d((px, py), cand_B):
                mid_x, mid_y = cand_A
            else:
                mid_x, mid_y = cand_B

            qm      = cls._quad(mid_x, mid_y)
            leg1_lbl = ("TRANSFER-LEG1 [radial rotate -> "
                        + cls._quad_str(*qm) + " nearest intermediate]")
            wps.append((mid_x, mid_y, z_safe, leg1_lbl))

            route = (cls._quad_str(*qp) + " -> "
                     + cls._quad_str(*qm) + " (radial J0) -> "
                     + cls._quad_str(*qd) + " (final)")

        elif x_cross or y_cross:
            route = (cls._quad_str(*qp) + " -> "
                     + cls._quad_str(*qd) + " (single-axis, direct)")
        else:
            route = cls._quad_str(*qp) + " -> same quadrant (direct)"

        wps.append((dx, dy, z_safe, "TRANSFER-FINAL"))
        return wps, route


# ==============================================================================
#  TaskExecutor
# ==============================================================================
class TaskExecutor:
    def __init__(self, params):
        self.p       = params
        self.robot   = RobotArm()
        self.gripper = Gripper(gtype=params.get("end_effector", "parallel"))
        self.planner = MotionPlanner(self.robot)
        self.logs    = []

    # ------------------------------------------------------------------
    def _move_to(self, label, pose):
        """Compute IK, plan trajectory, update joint state. Returns True on success."""
        target_q, status = self.robot.inverse_kinematics(pose)
        if target_q is None:
            logger.error("FAILURE at %s: %s", label, status)
            return False

        achieved = self.robot.forward_kinematics(target_q)
        pos_err_mm = np.linalg.norm(achieved[:3, 3] - pose[:3, 3]) * 1000.0

        self.planner.plan(self.robot.current_joints, target_q)     # plan (use traj in real hw)
        self.robot.current_joints = target_q

        logger.info("[%s] XYZ=%s | Pos err=%.2f mm | Status: %s",
                    label, np.round(pose[:3, 3], 4), pos_err_mm, status)
        self.logs.append("[%s] Joints=%s | Pos_err=%.2f mm"
                         % (label, np.round(target_q, 3), pos_err_mm))
        return True

    # ------------------------------------------------------------------
    def execute_sequence(self):
        logger.info("========== Starting Pick-and-Place Sequence ==========")
        p = self.p

        # --- Pre-computation -----------------------------------------
        Xo, Yo, Zo    = p["object_pos"]
        L,  W,  H     = p["object_dim"]
        Xp, Yp, _     = p["pick_pos"]
        Xpl, Ypl, Zpl = p["place_pos"]
        Zsafe = p["safe_height"]
        Cg    = p["gripper_clearance"]

        Xg, Yg, Zg = Xo, Yo, Zo + H/2.0 + Cg   # grasp point
        Zplace      = Zpl + H/2.0                 # place contact height

        # --- Orientation lock ----------------------------------------
        R, P, Y   = p["object_ori"]
        R_locked  = MotionPlanner.rpy_to_matrix(R, P, Y)
        ori_desc  = ("R=%.1fdeg P=%.1fdeg Y=%.1fdeg"
                     % (np.degrees(R), np.degrees(P), np.degrees(Y)))
        logger.info("[ORI LOCK] %s -- held constant for ALL waypoints", ori_desc)

        def wp(x, y, z):
            return MotionPlanner.get_pose_locked(x, y, z, R_locked)

        # --- Quadrant-aware transfer routing --------------------------
        transfer_wps, route = QuadrantRouter.get_transfer_waypoints(
            pick_xy  = (Xo, Yo),
            place_xy = (Xpl, Ypl),
            z_safe   = Zsafe,
        )
        logger.info("[QUADRANT ROUTER] %s", route)
        logger.info("[QUADRANT ROUTER] Transfer legs: %d", len(transfer_wps))
        for leg in transfer_wps:
            tag = "Rotate+Translate" if "LEG1" in leg[3] else "Final move     "
            logger.info("  %-18s -> XY=(%.3f, %.3f)  [%s]",
                        tag, leg[0], leg[1], leg[3])

        # --- Build full sequence --------------------------------------
        sequence = [
            # (label, pose_or_None, action_or_None)
            ("HOME",     None,             "home"),
            ("PRE-PICK", wp(Xp,Yp,Zsafe), None),
            ("APPROACH", wp(Xg,Yg,Zg),    None),
            ("GRASP",    None,             "close"),
            ("LIFT",     wp(Xo,Yo,Zsafe), None),
        ]

        # Inject quadrant-aware transfer legs
        for (tx, ty, tz, tlabel) in transfer_wps:
            sequence.append((tlabel, wp(tx, ty, tz), None))

        sequence += [
            ("PLACE",   wp(Xpl, Ypl, Zplace), None),
            ("RELEASE", None,                  "open"),
            ("RETRACT", wp(Xpl, Ypl, Zsafe),   None),
            ("RETURN",  None,                  "home"),
        ]

        # --- Execute --------------------------------------------------
        for label, pose, action in sequence:
            if action == "close":
                self.gripper.toggle("close")
                self.logs.append("[%s] Gripper CLOSED | Ori: %s" % (label, ori_desc))
                continue
            if action == "open":
                self.gripper.toggle("open")
                self.logs.append("[%s] Gripper OPENED | Placed @ %s" % (label, ori_desc))
                continue
            if action == "home":
                self.robot.current_joints = self.robot.home_position.copy()
                logger.info("[%s] Returned to home joints", label)
                self.logs.append("[%s] Joints: %s" % (label, np.round(self.robot.home_position, 3)))
                continue

            if not self._move_to(label, pose):
                return "FAILURE"

        return "SUCCESS"


# ==============================================================================
#  Helpers
# ==============================================================================
def _mat_to_rpy(R):
    """3x3 rotation matrix -> (roll, pitch, yaw) degrees."""
    pitch = np.arctan2(-R[2, 0], np.sqrt(R[2, 1]**2 + R[2, 2]**2))
    if abs(np.cos(pitch)) < 1e-6:
        roll, yaw = 0.0, np.arctan2(R[0, 1], R[1, 1])
    else:
        roll = np.arctan2(R[2, 1], R[2, 2])
        yaw  = np.arctan2(R[1, 0], R[0, 0])
    return np.degrees([roll, pitch, yaw])


# ==============================================================================
#  Entry point
# ==============================================================================
if __name__ == "__main__":
    # ------------------------------------------------------------------
    #  DEMO
    #  Pick  (20, 20, 30) mm  =  (0.020, 0.020, 0.030) m  -> Q++
    #  Place (-20,-30, 30) mm = (-0.020,-0.030, 0.030) m  -> Q--
    #
    #  Quadrant route auto-selected by QuadrantRouter:
    #    Q++ -> nearest intermediate (Q-+) -> Q--
    #    Leg-1: rotate base joint to Q-+ keeping Y of pick
    #    Leg-2: full IK move to Q-- final position
    # ------------------------------------------------------------------
    params = {
        "object_pos":   ( 0.020,  0.020,  0.030),   # pick  (20, 20, 30) mm
        "object_dim":   (0.05, 0.05, 0.10),          # L W H metres
        "object_ori":   (0.1, 0.1, 0.3),             # Roll Pitch Yaw radians -- LOCKED
        "pick_pos":     ( 0.020,  0.020,  0.030),
        "place_pos":    (-0.020, -0.030,  0.030),    # place (-20,-30, 30) mm
        "safe_height":  0.120,                        # transit Z (m)
        "gripper_clearance": 0.010,
        "end_effector": "parallel",
    }

    executor = TaskExecutor(params)
    result   = executor.execute_sequence()

    Ro, Po, Yo = params["object_ori"]
    sep = "=" * 65
    print("\n" + sep)
    print("  PICK & PLACE STATUS  :  %s" % result)
    print("  OBJECT ORIENTATION   :  Roll=%.1fdeg  Pitch=%.1fdeg  Yaw=%.1fdeg"
          % (np.degrees(Ro), np.degrees(Po), np.degrees(Yo)))
    print("  ORIENTATION POLICY   :  LOCKED -- same at pick AND place")
    print("  TRANSFER STRATEGY    :  Quadrant-aware radial rotation (2-leg)")
    print(sep)
    for log in executor.logs:
        print(log)
    print(sep)
