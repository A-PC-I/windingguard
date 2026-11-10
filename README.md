# WindingGuard

Lightweight radial-continuity QA for TIFXYZ papyrus surface traces.

## What it does

WindingGuard examines a TIFXYZ surface mesh relative to a supplied scroll umbilicus
and assigns local inspection-priority scores based on radial continuity.

The basic idea is deliberately simple:

- points on a locally continuous winding should usually change radial distance
  from the scroll axis smoothly;
- unusually large or sustained changes in radial position may indicate a region
  worth inspecting;
- WindingGuard reports those regions for review.

WindingGuard does **not** modify the mesh.

## What it does not do

WindingGuard is **not**:

- a sheet-switch detector;
- a surface tracer;
- a replacement for spiral fitting or VC3D;
- an ink detector;
- a machine-learning model.

A high score means:

> "This region is radially unusual relative to its local neighbourhood."

It does **not** mean:

> "This region is proven to be on the wrong winding."

## Input

WindingGuard v0.1 requires:

1. A TIFXYZ surface directory containing:

   - `x.tif`
   - `y.tif`
   - `z.tif`
   - optional `mask.tif`

2. An `umbilicus.json` file containing control points for the scroll axis.

At inference time WindingGuard uses mesh coordinates and the umbilicus only.
It does not use winding labels.

## Usage

```bash
python winding_guard_v0_1.py \
  --mesh path/to/tifxyz \
  --umbilicus path/to/umbilicus.json \
  --out winding_guard.csv


--window       Rolling local-baseline window (default: 11)
--abs-floor    Minimum radial jump before priority can increase (default: 6.0)
--k-shift      Neighbourhood used for sustained level-shift scoring (default: 5)


axis
index
median_r
p10_r
p90_r
iqr_r
valid_n
delta_r
local_median_delta
local_mad
relative_score
absolute_gate
spike_score
level_shift
shift_persistence
review_priority

Both TIFXYZ grid axes are scored independently.
review_priority ranges from 0 to 1 and should be interpreted only as an inspection-priority score.
Validation status
WindingGuard is experimental.
During development, radial continuity was evaluated on public PHerc. Paris. 4 winding annotations.
A radius-blind hold-out was constructed before radial distance was examined:
•800 same-winding point pairs
•400 adjacent-winding (Δwind = 1) point pairs
•pair selection used spatial proximity and Z proximity, not radial distance
On this locked set, radial difference produced:
•ROC AUC: 0.800
•recall at ≤5% false-positive rate: 0.547
•recall at ≤10% false-positive rate: 0.611
•precision within the highest-scoring 10%: 0.975
These results support radial continuity as a potentially useful review-prioritisation signal.
They do not support treating WindingGuard as a standalone classifier of sheet switches.
Ablation: surface normals
Surface-normal disagreement was tested on the subset of locked pairs for which suitable mesh geometry was available.
Normal continuity did not improve discrimination and was discarded from v0.1.
WindingGuard therefore remains a radial-only method.
Limitations
Current validation is limited.
In particular:
•the radius-blind hold-out used sparse winding annotation points rather than a large set of known historical mesh switches;
•performance has not been established across different scrolls;
•local geometry may vary substantially between regions;
•a radial discontinuity can have causes other than a winding error;
•a genuine winding error may occur without producing a strong radial anomaly.
The most useful next validation would be against real meshes containing independently identified and corrected sheet switches.
Design philosophy
WindingGuard is intentionally:
•small;
•deterministic;
•explainable;
•CPU-friendly;
•downstream of existing tracing;
•conservative about what its score means.
The aim is not to replace physical or geometric evidence.
The aim is to help answer a smaller question:
Where should a reviewer look first?
Data provenance
Development and validation used public Vesuvius Challenge geometry and winding annotations for PHerc. Paris. 4.
No Vesuvius Challenge CT data, meshes, or annotations are redistributed in this repository.
Users should obtain source data from the Vesuvius Challenge under the terms applicable to those datasets.
Status
v0.1 — experimental
Current interpretation:
•radial continuity: promising as review-prioritisation QA;
•surface normals: tested and discarded;
•standalone sheet-switch detection: not demonstrated.
Author
Paul Curtis
Independent Researcher
