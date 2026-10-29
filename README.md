# Cartilage Indentation Analysis

A small **Python package** to process spherical **micro-indentation** measurements
of articular cartilage (Bioindenter `.TXT` files) and extract mechanical
parameters. The pipeline performs baseline-drift correction, contact-point
detection, **Hertz** elastic fitting of monotonic (mono) indentation, and
**1-term Prony** viscoelastic fitting of stress-relaxation curves. Native is compared individually with Crosslinked, Degraded, and
Degraded_after_crosslinked. Degraded and Crosslinked are also each compared with
Degraded_after_crosslinked, with an additional four-treatment overlay per test type, and every fit
parameter is saved with its curve metadata. The notebook supports either Excel
metadata or metadata parsed directly from filenames in one or multiple folders.

---

## Repository Structure

```
CartilageIndentationAnalysis/
├── config.py                     # user settings: paths + analysis parameters (edit this)
├── cartilage_indentation/        # the package
│   ├── io_utils.py               # read raw Bioindenter .TXT files
│   ├── dataset.py                # Excel/filename metadata, source tracking, groups and comparisons
│   ├── preprocessing.py          # contact detection, zeroing, mono baseline-drift correction
│   ├── hertz.py                  # Hertz model + fitting (moving-regression / 50%-max contact point)
│   ├── prony.py                  # 1-term Prony model + stress-relaxation fitting
│   ├── plotting.py               # raw-vs-corrected, treatment comparison, and fit figures
│   └── results.py                # save metadata, fit parameters and preprocessing flags
├── notebooks/
│   └── analysis.ipynb            # interactive interface: imports the package, runs the analysis
├── scripts/
│   └── run_analysis.py           # command-line entry point: runs the whole pipeline
├── data/
│   ├── README.md                     # detailed guide to organize the data
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

**1. Raw Bioindenter files** — one `.TXT` per curve. Tab-separated; a
`Measured values` header line precedes the columns
`time, displ, load, ref_load, segm`. Units: displacement in **µm**, load in
**mN**, time in **s**. The instrument `segm` column labels the test phases
(see *Notes*).

**2. Choose a metadata source:** the notebook provides both options below.
The command-line entry point continues to use Excel.

### Option A: filenames, including multiple folders

Use `INPUT_MODE = "filenames"` in the first block of
[`notebooks/analysis.ipynb`](notebooks/analysis.ipynb). No input Excel or copying of
raw files is required. Names must follow this pattern (case-insensitive):

```text
Measurement_3_Sample_A_native_mono_1.TXT
Measurement_3_Sample_B_degraded_after_crosslinking_stress_relaxation_41.TXT
```

The parser extracts `sample_name`, `measurement`, `specimen`, `status`,
`test_type`, and `curve_number`, then derives the treatment and plot group.
`degraded_after_crosslinking` maps to `Degraded_after_crosslinked`.
Legends use codes such as `(M3SA)` = Measurement 3, Sample A.

Add one entry per raw-data folder:

```python
FILENAME_SOURCES = [
    {"path": Path("/path/to/measurement_3"), "batch": "20261029",
     "label": "M3", "recursive": False},
    {"path": Path("/path/to/measurement_1"), "batch": "20261022",
     "label": "M1", "recursive": True},
    {"path": Path("/path/to/measurement_2/raw"), "batch": "20261026",
     "label": "M2", "recursive": False},
]
```

`recursive=True` scans subfolders. Each label must be unique and use letters,
numbers, underscores or hyphens. All selected `.TXT` files must match the naming
pattern; `.mit` files are ignored. Do not select archive/copy folders containing
the same experiment again. Overlapping selections of the same physical file are
rejected; separate copied files are not automatically deduplicated by content.

Global `sample_id` values are assigned across all sources. Original trailing
numbers may repeat and remain in `curve_number`. The result table preserves
`source_label`, `source_root`, `source_file_name`, and `source_path`.
In multi-source runs, per-group plots distinguish source, specimen, treatment
and test type. Treatment comparisons pool matching treatment/test-type curves
across sources. They do not imply biological pairing or statistical significance.

Results default to `Analysis_Output/<folder>/` for one source, or
`Analysis_Output/combined_filenames_<id>/` for multiple sources. Set
`ANALYSIS_OUTPUT_ROOT` to override this. Fits are saved to `analysis_results.xlsx`;
optional optimization exports also preserve source identity in CSV names.

### Option B: Excel metadata (original workflow)

Set `INPUT_MODE = "excel"` and configure `RAW_ROOT`, `DATASET_ROOT` and
`EXCEL_SAMPLE_SHEET` in the notebook, or use the command-line entry point.
`sample_groups.xlsx` requires these columns:

| column | meaning |
| --- | --- |
| `file_name` | raw `.TXT` path relative to the raw-data root |
| `sample_id` | unique integer curve ID |
| `treatment` | e.g.`Native` `Crosslinked`, `Degraded` ,`Degraded_after_crosslinked` |
| `test_type` | `mono` or `stress_relaxation` |
| `Group` | label for per-group plots; comparisons pool samples by treatment and test_type |

The dataset used here ships with the repository: raw files in `data/raw/`, metadata in
`data/sample_groups.xlsx`. `data/sample_groups_template.xlsx` shows the required format.

> **New to the format?** See **[`data/README.md`](data/README.md)** — it explains every column,
> the treatment comparison rules, and how to run the pipeline on your own data in 3 steps.

---

## Usage

1. (Optional) Edit **`config.py`** — by default it reads the bundled data in `data/`, so
   no path changes are needed. Adjust the analysis parameters there if desired. To use data
   stored elsewhere, change `SAMPLE_SHEET` / `RAW_DATA_DIR`. Output folders are created automatically.
2. From the repository root, run:

```
python scripts/run_analysis.py
```

This preprocesses every file, saves raw-vs-corrected and treatment comparison figures,
fits the mono loading curves (Hertz, two contact-point methods) and the
stress-relaxation curves (1-term Prony), and appends the fit parameters to the
metadata sheet.

Or, for an **interactive run**, open `notebooks/analysis.ipynb` — it imports the same
package and runs each step in cells, showing the fitted parameters and figures inline.
Choose the filename or Excel option first, review the metadata preview, then run
the exclusion block and Steps 2–6. After changing sources, restart the kernel and
rerun in order. The default filename sources now include M1/20261022 Sample A,
M2/20261026 Sample A, and M3/20261029 specimens. The M2 source selects the canonical
`raw/` folder rather than its duplicate exports.

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

1. **Load & group** (`dataset.py`) — read Excel metadata or parse filenames across selected sources; assign curve IDs, track provenance and build treatment comparisons.
2. **Contact detection & zeroing** (`preprocessing.py`) — contact = first row where load stays above a threshold for a few consecutive rows; `time`/`displ` are zeroed at contact and `load` is referenced to the pre-contact baseline.
3. **Drift correction (complete mono only)** — estimate the pre-contact and post-retract baselines and subtract `F_pre + slope * (t − t_pre)`. Incomplete mono curves use contact zeroing only, as explained below.
4. **Hertz fit (mono)** (`hertz.py`) — `F = (4/3)·E*·√R·(d − cp)^1.5` on the loading ramp, with two ways to define the contact point `cp`: **moving regression** on the linearized curve `F^(2/3)` vs `d`, or **data above 50 % of peak load**.
5. **Prony fit (SR)** (`prony.py`) — `F(t)/F0 = (1 − g1) + g1·e^(−t/τ1)` on the relaxation phase (peak → `SR_FIT_MAX_TIME`).
6. **Save** (`results.py`) — figures under `OUTPUT_ROOT`; filename mode writes `analysis_results.xlsx`. Excel mode updates the input sheet unless exclusions require a separate result sheet. Preprocessing reports and incomplete-curve flags accompany the fitted parameters.

## Incomplete mono curves and failed preprocessing

A complete mono cycle must contain loading (`segm 1`), at least 3 subsequent
unloading points (`segm 3`) and at least 15 trailing retract points (`segm 4`) to
provide the post-test baseline. A loading-only curve, truncated unloading, or a
missing retract baseline is classified as incomplete.

**Incomplete mono curves skip drift correction and use contact zeroing only.**
They remain eligible for both Hertz methods, which use only `segm 1`. The final
loading force is not treated as a zero-force post-test baseline. Plots mark these
curves `[incomplete; no drift correction]`; tables record `mono_complete`,
`mono_incomplete_reason`, `drift_correction_applied`, and `preprocessing_method`.
Incompleteness alone does not exclude a curve or guarantee a good fit.

The notebook defaults to `PREPROCESS_ON_ERROR = "skip"`: a curve that cannot be
preprocessed is listed in `preprocessing_report.csv`, omitted from plots/fits,
and kept in results with a failed status, reason and blank fit values. Set
`"raise"` for strict behavior. The CLI remains strict by default. Manual exclusions
in Step 1a omit selected curves entirely from filtered results and record a
separate exclusion list. Contact detection still defaults to 3 consecutive points
above 6 µN; SR preprocessing is unchanged.

---

## Pinned / Important Variables

All in **`config.py`**:

- **Paths:** `DATA_ROOT`, `SAMPLE_SHEET`, `RAW_DATA_DIR`; outputs under `OUTPUT_ROOT`.
- **Probe / material:** `PROBE_RADIUS = 500` µm, `POISSON_RATIO = 0.25`.
- **Stress-relaxation segments:** `TARGET_SEGS_SR = [5, 6, 7, 8]`.
- **Contact detection:** `CONTACT_THRESHOLD = 6` (µN), `CONTACT_MIN_CONSEC = 3` rows.
- **p50 contact limits:** `P50_CP_BOUNDS_UM = (-20, 20)` relative to contact zero; these are configurable working limits. Boundary solutions show `[cp bound]` and save `cp_at_bound_p50` plus the effective limits.
- **Prony window:** `SR_FIT_MAX_TIME = 120` s (peak → this time).

**Output columns** added to the metadata sheet:
`Es_moving, cp_moving, r2_moving, Es_p50, cp_p50, r2_p50` (mono) and
`g1, ge, tau1_s, F0_mN, r2_prony` (stress-relaxation). Preprocessing status,
incomplete-curve metadata and p50 boundary diagnostics are also saved. Re-running
refreshes generated fields while preserving other metadata.

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
