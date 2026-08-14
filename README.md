# Cartilage Indentation Analysis

A small **Python package** to process spherical **micro-indentation** measurements
of articular cartilage (Bioindenter `.TXT` files) and extract mechanical
parameters. The pipeline performs baseline-drift correction, contact-point
detection, **Hertz** elastic fitting of monotonic (mono) indentation, and
**1-term Prony** viscoelastic fitting of stress-relaxation curves. Native and
crosslinked (UV / riboflavin) groups are compared automatically, and every fit
parameter is written back into the sample metadata sheet.

---

## Repository Structure

```
CartilageIndentationAnalysis/
├── config.py                     # user settings: paths + analysis parameters (edit this)
├── cartilage_indentation/        # the package
│   ├── io_utils.py               # read raw Bioindenter .TXT files
│   ├── dataset.py                # SampleIndex: read metadata sheet, group files, build Native/UV pairs
│   ├── preprocessing.py          # contact detection, zeroing, mono baseline-drift correction
│   ├── hertz.py                  # Hertz model + fitting (moving-regression / 50%-max contact point)
│   ├── prony.py                  # 1-term Prony model + stress-relaxation fitting
│   ├── plotting.py               # raw-vs-corrected, Native-vs-UV, and fit figures
│   └── results.py                # write fit parameters back into the metadata sheet
├── scripts/
│   └── run_analysis.py           # entry point — runs the whole pipeline
├── data/
│   ├── raw/                          # raw Bioindenter .TXT files (one per sample)
│   ├── sample_groups.xlsx            # sample metadata + fit results
│   └── sample_groups_template.xlsx   # example metadata sheet (format only)
├── figures/                      # place workflow diagrams / exported figures here
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.9+
- `numpy`, `pandas`, `scipy`, `matplotlib`, `openpyxl`

```
pip install -r requirements.txt
```

---

## Input Data

**1. Raw Bioindenter files** — one `.TXT` per sample. Tab-separated; a
`Measured values` header line precedes the columns
`time, displ, load, ref_load, segm`. Units: displacement in **µm**, load in
**mN**, time in **s**. The instrument `segm` column labels the test phases
(see *Notes*).

**2. Sample metadata sheet** — an Excel file (`sample_groups.xlsx`) with columns:

| column | meaning |
| --- | --- |
| `file_name` | raw `.TXT` file name |
| `sample_id` | integer sample id |
| `treatment` | e.g. `Clinical Riboflavin Part 1 Native`, `Sigma Riboflavin UV` |
| `test_type` | `mono` or `stress_relaxation` |
| `Group` | grouping label (treatment + test type), used for plots and Native/UV pairing |

The dataset used here ships with the repository: raw files in `data/raw/`, metadata in
`data/sample_groups.xlsx`. `data/sample_groups_template.xlsx` shows the required format.

---

## Usage

1. (Optional) Edit **`config.py`** — by default it reads the bundled data in `data/`, so
   no path changes are needed. Adjust the analysis parameters there if desired. To use data
   stored elsewhere, change `SAMPLE_SHEET` / `RAW_DATA_DIR`. Output folders are created automatically.
2. From the repository root, run:

```
python scripts/run_analysis.py
```

This preprocesses every file, saves raw-vs-corrected and Native-vs-UV figures,
fits the mono loading curves (Hertz, two contact-point methods) and the
stress-relaxation curves (1-term Prony), and appends the fit parameters to the
metadata sheet.

The package can also be imported directly, e.g.:

```python
import config as cfg
from cartilage_indentation.dataset import SampleIndex
from cartilage_indentation.preprocessing import preprocess_all

index = SampleIndex(cfg.SAMPLE_SHEET, cfg.RAW_DATA_DIR)
mono_data, sr_data = preprocess_all(index, cfg)
```

---

## Workflow

1. **Load & group** (`dataset.py`) — read the metadata sheet, map each `.TXT` to its group, build Native-vs-UV pairs.
2. **Contact detection & zeroing** (`preprocessing.py`) — contact = first row where load stays above a threshold for a few consecutive rows; `time`/`displ` are zeroed at contact and `load` is referenced to the pre-contact baseline.
3. **Drift correction (mono only)** — mono tests are slow, so a slow linear baseline drift is removed using the two "should-be-zero" baselines (pre-contact and post-retract): `F_true(t) = F(t) − tan(α)·(t − t0)`.
4. **Hertz fit (mono)** (`hertz.py`) — `F = (4/3)·E*·√R·(d − cp)^1.5` on the loading ramp, with two ways to define the contact point `cp`: **moving regression** on the linearized curve `F^(2/3)` vs `d`, or **data above 50 % of peak load**.
5. **Prony fit (SR)** (`prony.py`) — `F(t)/F0 = (1 − g1) + g1·e^(−t/τ1)` on the relaxation phase (peak → `SR_FIT_MAX_TIME`).
6. **Save** (`results.py`) — figures under `OUTPUT_ROOT`; per-sample fit parameters appended to the metadata sheet.

---

## Pinned / Important Variables

All in **`config.py`**:

- **Paths:** `START_DIR`, `SAMPLE_SHEET`, `RAW_DATA_DIR`; outputs under `OUTPUT_ROOT`.
- **Probe / material:** `PROBE_RADIUS = 500` µm, `POISSON_RATIO = 0.25`.
- **Stress-relaxation segments:** `TARGET_SEGS_SR = [5, 6, 7, 8]`.
- **Contact detection:** `CONTACT_THRESHOLD = 6` (mN), `CONTACT_MIN_CONSEC = 3` rows.
- **Prony window:** `SR_FIT_MAX_TIME = 120` s (peak → this time).

**Output columns** added to the metadata sheet:
`Es_moving, cp_moving, r2_moving, Es_p50, cp_p50, r2_p50` (mono) and
`g1, ge, tau1_s, F0_mN, r2_prony` (stress-relaxation). Re-running drops and
re-adds only these columns; all other columns are kept.

---

## Notes / Best Practices

- **Instrument segments (`segm`):** `1` = loading ramp, `2` = hold, `3` = unloading, `4` = retract for mono; stress-relaxation uses `[5, 6, 7, 8]`. The Hertz fit uses only the loading ramp (`segm 1`); the hold and retract are excluded.
- **`R²`** is the coefficient of determination, `1 − SS_res/SS_tot` (not the squared Pearson correlation).
- Raw data and generated output folders are **not** version-controlled (see `.gitignore`). Set the paths in `config.py` for your machine.

---

## Acknowledgements

This pipeline was developed by **Keke Xia**, building on the work of colleagues in the group:

- **Tatiana Kochetkova** — the analysis approach is based on her original fitting scripts and follows many of her methodological suggestions, including the load-threshold contact detection, the two-point baseline-drift correction (`tan(α) = ΔF/Δt`), the moving-regression contact point, and the FEBio contact-area extraction.
- **Estelle Steiner** — the sample grouping and plotting were adapted from her original processing code; she performed the indentation experiments and provided the data.

Any errors introduced while re-writing and reorganizing the code are my own.

---

**Author:** Keke Xia 
