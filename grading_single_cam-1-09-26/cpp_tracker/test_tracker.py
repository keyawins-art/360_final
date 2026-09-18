"""
Smoke test for cashew_tracker_core C++ module.

Simulates a cashew moving down a belt at constant speed,
then introduces a rotation-induced centroid jump to verify
that the Kalman tracker maintains the same ID.
"""

import time
import sys
import os

# Add parent directory so we can import the .pyd from grading/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import cashew_tracker_core
except ImportError:
    print("[FAIL] cashew_tracker_core not built. Run build.bat first.")
    sys.exit(1)

print("=" * 60)
print("  cashew_tracker_core Smoke Test")
print("=" * 60)

tracker = cashew_tracker_core.CashewTracker(
    120.0, 2500.0, 320.0, 8, 35.0, 8.0
)

t = time.perf_counter()

# --- Test 1: Single cashew moving straight down ---
print("\n[TEST 1] Single cashew moving straight down (20 frames)")
prev_id = None
for i in range(20):
    d = cashew_tracker_core.Detection()
    d.x = 300.0
    d.y = 100.0 + i * 15.0  # Moving down at 15px per frame
    d.size_mm = 22.0
    out = tracker.update([d], t + i * 0.01)

    if out:
        tr = out[0]
        if prev_id is not None and tr.id != prev_id:
            print(f"  [FAIL] ID changed from {prev_id} to {tr.id} at frame {i}")
        prev_id = tr.id
        print(
            f"  frame={i:2d} id={tr.id} x={tr.x:.1f} y={tr.y:.1f} "
            f"vx={tr.vx:.1f} vy={tr.vy:.1f} "
            f"speed={tr.speed_px_s:.1f} det_idx={tr.det_index}"
        )

print(f"  [{'PASS' if prev_id == 1 else 'FAIL'}] Maintained ID={prev_id} through 20 frames")

# --- Test 2: Rotation-induced centroid jump ---
print("\n[TEST 2] Rotation-induced centroid jump")
tracker.reset()
t2 = time.perf_counter()

# Normal movement for 10 frames
for i in range(10):
    d = cashew_tracker_core.Detection()
    d.x = 200.0
    d.y = 50.0 + i * 12.0
    d.size_mm = 20.0
    tracker.update([d], t2 + i * 0.015)

# Sudden centroid shift (cashew rotates — centroid moves 30px laterally)
d = cashew_tracker_core.Detection()
d.x = 230.0  # jumped 30px right
d.y = 50.0 + 10 * 12.0 + 12.0  # still moving down
d.size_mm = 20.0
out = tracker.update([d], t2 + 10 * 0.015)

if out:
    tr = out[0]
    print(f"  After jump: id={tr.id} x={tr.x:.1f} y={tr.y:.1f} det_idx={tr.det_index}")
    print(f"  [{'PASS' if tr.id == 1 else 'FAIL'}] Rotation jump: ID={'maintained' if tr.id == 1 else 'LOST'}")
else:
    print("  [FAIL] No tracks returned after rotation jump")

# --- Test 3: Two close cashews should NOT merge IDs ---
print("\n[TEST 3] Two close cashews (100px apart)")
tracker.reset()
t3 = time.perf_counter()

id_a_history = []
id_b_history = []

for i in range(15):
    d1 = cashew_tracker_core.Detection()
    d1.x = 200.0
    d1.y = 50.0 + i * 10.0
    d1.size_mm = 18.0

    d2 = cashew_tracker_core.Detection()
    d2.x = 300.0
    d2.y = 70.0 + i * 10.0
    d2.size_mm = 25.0

    out = tracker.update([d1, d2], t3 + i * 0.012)

    for tr in out:
        if abs(tr.x - (200.0 + (tr.x - 200.0))) < 80:
            if tr.det_index == 0:
                id_a_history.append(tr.id)
            elif tr.det_index == 1:
                id_b_history.append(tr.id)

    if out and len(out) >= 2:
        print(f"  frame={i:2d} | track1: id={out[0].id} ({out[0].x:.0f},{out[0].y:.0f}) | "
              f"track2: id={out[1].id} ({out[1].x:.0f},{out[1].y:.0f})")

unique_a = set(id_a_history)
unique_b = set(id_b_history)
ids_stable = len(unique_a) <= 1 and len(unique_b) <= 1 and unique_a != unique_b
print(f"  [{'PASS' if ids_stable else 'WARN'}] Cashew A IDs: {unique_a}, Cashew B IDs: {unique_b}")

# --- Test 4: Missing frames recovery ---
print("\n[TEST 4] Missing frames recovery (3-frame gap)")
tracker.reset()
t4 = time.perf_counter()

# Normal for 5 frames
for i in range(5):
    d = cashew_tracker_core.Detection()
    d.x = 400.0
    d.y = 100.0 + i * 20.0
    d.size_mm = 21.0
    tracker.update([d], t4 + i * 0.02)

# 3 frames with NO detection (cashew temporarily invisible)
for i in range(3):
    tracker.update([], t4 + (5 + i) * 0.02)

# Cashew reappears at predicted location
d = cashew_tracker_core.Detection()
d.x = 400.0
d.y = 100.0 + 8 * 20.0  # where it should be if continuing at same speed
d.size_mm = 21.0
out = tracker.update([d], t4 + 8 * 0.02)

if out:
    tr = out[0]
    print(f"  After 3-frame gap: id={tr.id} missed={tr.missed} det_idx={tr.det_index}")
    print(f"  [{'PASS' if tr.id == 1 else 'FAIL'}] Recovery: ID={'maintained' if tr.id == 1 else 'LOST'}")
else:
    print("  [FAIL] No tracks returned after gap")

print("\n" + "=" * 60)
print("  Smoke test complete.")
print("=" * 60)
