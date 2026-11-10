#!/usr/bin/env python3
"""
WindingGuard v0.1
Local radial continuity scorer for TIFXYZ surface patches.

Scores inconsistency relative to a rolling local baseline.
Does not claim a high score is a verified sheet switch.
Uses only mesh coordinates + umbilicus at inference.

Frozen design:
- validity: z > 0 (+ optional mask.tif)
- both grid axes scored independently
- distribution quantiles retained
- absolute floor + relative score
- level-shift / persistence distinction
- review_priority (0-1), not a binary label
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def load_umbilicus(path):
    with open(path) as f:
        umb = json.load(f)
    pts = sorted(umb["control_points"], key=lambda p: p["z"])
    return (
        np.array([p["z"] for p in pts], dtype=np.float64),
        np.array([p["x"] for p in pts], dtype=np.float64),
        np.array([p["y"] for p in pts], dtype=np.float64),
    )


def radial(x, y, z, uz, ux, uy):
    return np.hypot(x - np.interp(z, uz, ux), y - np.interp(z, uz, uy))


def load_mesh(mesh_dir):
    mesh_dir = Path(mesh_dir)
    x = np.array(Image.open(mesh_dir / "x.tif"), dtype=np.float32)
    y = np.array(Image.open(mesh_dir / "y.tif"), dtype=np.float32)
    z = np.array(Image.open(mesh_dir / "z.tif"), dtype=np.float32)
    valid = z > 0
    mask_path = mesh_dir / "mask.tif"
    if mask_path.exists():
        mask = np.array(Image.open(mask_path))
        valid &= mask > 0
    return x, y, z, valid


def column_stats(xcol, ycol, zcol, uz, ux, uy):
    r = radial(xcol, ycol, zcol, uz, ux, uy)
    return {
        "median": float(np.median(r)),
        "p10": float(np.percentile(r, 10)),
        "p90": float(np.percentile(r, 90)),
        "iqr": float(np.percentile(r, 75) - np.percentile(r, 25)),
        "n": int(len(r)),
    }


def score_axis(x, y, z, valid, uz, ux, uy, window=11, abs_floor=6.0, k_shift=5):
    """Score one grid axis. Columns are the second dimension."""
    records = []
    prev_medians = []

    for c in range(x.shape[1]):
        m = valid[:, c]
        if m.sum() < 4:
            continue
        st = column_stats(x[:, c][m], y[:, c][m], z[:, c][m], uz, ux, uy)
        med = st["median"]

        if len(prev_medians) >= 3:
            recent = prev_medians[-window:]
            deltas = np.abs(np.diff(recent))
            local_med = float(np.median(deltas))
            local_mad = float(np.median(np.abs(deltas - local_med))) + 1e-6
            delta = abs(med - prev_medians[-1])
            rel = delta / (local_med + local_mad)
            abs_ok = delta >= abs_floor
        else:
            delta = local_med = local_mad = rel = 0.0
            abs_ok = False

        # Persistence over actual observations only
        recent_flags = [rec["elevated"] for rec in records[-4:]]
        current_elevated = bool(rel > 2.5 and abs_ok)
        history = recent_flags + [current_elevated]
        shift_persistence = sum(history) / len(history)

        # Level shift: before vs after (requires looking ahead)
        # Computed in a second pass below; placeholder for now
        records.append({
            "index": c,
            "median_r": med,
            "p10_r": st["p10"],
            "p90_r": st["p90"],
            "iqr_r": st["iqr"],
            "valid_n": st["n"],
            "delta_r": delta,
            "local_median_delta": local_med,
            "local_mad": local_mad,
            "relative_score": rel,
            "absolute_gate": int(abs_ok),
            "elevated": current_elevated,
            "shift_persistence": shift_persistence,
            "level_shift": 0.0,  # filled in second pass
            "spike_score": 0.0,
            "review_priority": 0.0,
        })
        prev_medians.append(med)

    # Second pass: level_shift using before/after medians
    medians = [rec["median_r"] for rec in records]
    for i, rec in enumerate(records):
        before = medians[max(0, i - k_shift):i]
        after = medians[i + 1:i + 1 + k_shift]
        if len(before) >= 3 and len(after) >= 3:
            level_shift = abs(np.median(after) - np.median(before))
        else:
            level_shift = 0.0
        rec["level_shift"] = float(level_shift)

        # Spike: large delta that returns (level_shift small)
        # Shift: large delta with sustained level change
        if rec["absolute_gate"]:
            rec["spike_score"] = rec["relative_score"] if level_shift < abs_floor else 0.0
            shift_component = min(1.0, level_shift / (abs_floor * 3))
        else:
            rec["spike_score"] = 0.0
            shift_component = 0.0

        # review_priority: only raised when absolute gate is open
        if rec["absolute_gate"]:
            rel_part = min(rec["relative_score"] / 5.0, 1.0)
            rec["review_priority"] = float(
                min(1.0, 0.35 * rel_part + 0.65 * shift_component * rec["shift_persistence"])
            )
        else:
            rec["review_priority"] = 0.0

    return records


def score_mesh(x, y, z, valid, uz, ux, uy, **kwargs):
    axis1 = score_axis(x, y, z, valid, uz, ux, uy, **kwargs)
    axis0 = score_axis(x.T, y.T, z.T, valid.T, uz, ux, uy, **kwargs)
    return {"axis1": axis1, "axis0": axis0}


def write_csv(results, out_path):
    fields = [
        "axis", "index", "median_r", "p10_r", "p90_r", "iqr_r", "valid_n",
        "delta_r", "local_median_delta", "local_mad", "relative_score",
        "absolute_gate", "spike_score", "level_shift", "shift_persistence",
        "review_priority",
    ]
    with open(out_path, "w") as f:
        f.write(",".join(fields) + "\n")
        for axis_name, records in results.items():
            for rec in records:
                row = [axis_name] + [rec.get(k, "") for k in fields[1:]]
                f.write(",".join(str(v) for v in row) + "\n")


def main():
    ap = argparse.ArgumentParser(description="WindingGuard v0.1")
    ap.add_argument("--mesh", required=True, help="TIFXYZ directory")
    ap.add_argument("--umbilicus", required=True, help="umbilicus.json")
    ap.add_argument("--out", default="winding_guard.csv")
    ap.add_argument("--window", type=int, default=11)
    ap.add_argument("--abs-floor", type=float, default=6.0)
    ap.add_argument("--k-shift", type=int, default=5)
    args = ap.parse_args()

    uz, ux, uy = load_umbilicus(args.umbilicus)
    x, y, z, valid = load_mesh(args.mesh)
    results = score_mesh(
        x, y, z, valid, uz, ux, uy,
        window=args.window, abs_floor=args.abs_floor, k_shift=args.k_shift,
    )
    write_csv(results, args.out)
    n1 = len(results["axis1"])
    n0 = len(results["axis0"])
    print(f"Wrote {n1} (axis1) + {n0} (axis0) records to {args.out}")


if __name__ == "__main__":
    main()
