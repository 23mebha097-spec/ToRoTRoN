import sys
try:
    print("Testing trimesh.collision...")
    import trimesh.collision
    print("Testing CollisionManager creation...")
    cm = trimesh.collision.CollisionManager()
    print("Collision test SUCCESSFUL.")
except Exception as e:
    print(f"COLLISION TEST FAILED: {e}")
    sys.exit(1)
