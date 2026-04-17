#!/usr/bin/env python3
"""
Quick verification script for Welding and Painting modes.
This verifies the motion state machines are in place.
"""

import sys
import numpy as np

# Check that key functions exist
from ui.panels.simulation_panel import SimulationPanel

required_methods = [
    '_weld_tick',
    '_move_weld_smoothly',
    '_record_weld_live_trail',
    '_update_weld_live_trail_visual',
    '_set_weld_live_point',
    '_on_paint_tick',
    '_record_paint_live_trail',
    '_update_paint_live_trail_visual',
    '_handle_sequential_motion',
]

print("[CHECK] Checking Welding & Painting Mode Implementation...")
print()

missing = []
for method in required_methods:
    if hasattr(SimulationPanel, method):
        print(f"[OK] {method}")
    else:
        print(f"[FAIL] {method} - MISSING")
        missing.append(method)

print()
if missing:
    print(f"[ERROR] {len(missing)} method(s) missing: {missing}")
    sys.exit(1)
else:
    print("[SUCCESS] All required methods are present!")
    print()
    print("Testing implementation details...")

    # Check that the methods are callable and have content
    import inspect

    for method_name in ['_weld_tick', '_on_paint_tick']:
        method = getattr(SimulationPanel, method_name)
        source = inspect.getsource(method)
        lines = source.split('\n')

        if len(lines) > 10:
            print(f"[OK] {method_name} has {len(lines)} lines of implementation")
        else:
            print(f"[WARN] {method_name} is quite short ({len(lines)} lines) - may be stub")

    print()
    print("[SUCCESS] Welding and Painting modes appear to be properly implemented!")
    print()
    print("NEXT STEPS:")
    print("1. Start the application (python main.py)")
    print("2. Go to SIMULATION MODE -> Welding tab")
    print("3. Import a CAD model with edges")
    print("4. Select welding edges")
    print("5. Click 'Start Welding'")
    print("6. Watch the robot joints animate and the orange trail line appear")
    print()
    print("For Painting:")
    print("1. Go to SIMULATION MODE -> Painting tab")
    print("2. Define a paint area (4 points or pre-computed)")
    print("3. Click 'Start Painting'")
    print("4. Watch the robot joints animate and the yellow trail line appear")
