# `data/` — inputs for the pipeline

## Notebook input from filenames

The notebook also supports raw files whose names contain the metadata:

```text
Measurement_3_Sample_A_native_mono_1.TXT
Measurement_3_Sample_B_degraded_after_crosslinking_stress_relaxation_41.TXT
```

The default workflow is `INPUT_MODE = "filenames"` for **both single-folder and
multi-folder analysis**. Excel is an optional reference/backup input mode.
Configure one or more folders in `FILENAME_SOURCES` in the first notebook block:

```python
from pathlib import Path

FILENAME_SOURCES = [
    {"path": Path("/Users/xkk/Desktop/ExprimentResultsRawDataIndentation /20261029_3"),
     "batch": "20261029", "label": "M3", "recursive": False},
    {"path": Path("/Users/xkk/Desktop/ExprimentResultsRawDataIndentation /20261022_26/20261022"),
     "batch": "20261022", "label": "M1", "recursive": True},
    {"path": Path("/Users/xkk/Desktop/ExprimentResultsRawDataIndentation /20261022_26/20261026/20261026/raw"),
     "batch": "20261026", "label": "M2", "recursive": False},
]
```

Keep just one entry for a single folder, or add further entries for future data.
`batch` records the date (not encoded in the filenames). `label` identifies the
source and must be unique, using letters/numbers/underscores/hyphens. Set
`recursive=True` to scan subfolders. `.mit` files are ignored; every selected
`.TXT` must match the pattern. No raw-data copying or input Excel is required.

The existing datasets use `Measurement_1_Sample_A` for 20261022 and
`Measurement_2_Sample_A` for 20261026. The M2 input above deliberately selects the
canonical files used by its original metadata, rather than recursively including
the other export copies in the enclosing folders. Select each experiment once.

The parser keeps `sample_name` (for example `Measurement_3_Sample_A`),
`measurement`, `specimen`, original `status`, and `curve_number`, and derives
`treatment`, `test_type`, and `Group`. `degraded_after_crosslinking` maps to the
existing treatment `Degraded_after_crosslinked`. Single-source groups distinguish
specimen, treatment and test type. With multiple sources, the source label is
also included in `Group` to keep identically named specimens separate in per-group
plots. Treatment comparisons still pool matching treatments/test types across
sources; these overlays are not statistical tests or biological pairing.

Each row retains `source_label`, `source_root`, `source_file_name` (relative to
its own folder), and `source_path` (absolute). The loader selects a common raw-data
root automatically and expresses `file_name` relative to it, so existing loading,
exclusion, preprocessing and fitting cells work with all selected folders.
Identical basenames in different folders are supported. Selecting the same physical
file twice through overlapping roots or symlinks raises an error. Separate copies
of the same data are not automatically deduplicated by content.

Plot legends use specimen codes, for example `Native #5 (M3SA)` where `M3SA`
means `Measurement_3_Sample_A`; `M3SB` means sample B from measurement 3.
Incomplete-curve and contact-bound flags remain visible. Batch dates are kept
in the metadata. Excel inputs can supply `sample_name` or use the same filename
pattern; older inputs without specimen information retain their batch labels.

`sample_id` is a unique sequential analysis ID, separate from the original curve
number, which may repeat. IDs are assigned in deterministic order, but can shift
if sources are reordered or files are added/removed. For exclusions, copy exact
`file_name` values from the metadata preview. Adding/removing sources can also
change the common root and these relative paths; review exclusions after changes.

No input Excel is created or read. Results are saved as `analysis_results.xlsx`
under `project/Analysis_Output/<folder>` for a single source, or
`project/Analysis_Output/combined_filenames_<id>` for multiple sources; override
this with `ANALYSIS_OUTPUT_ROOT`. Different source configurations get separate
default output directories. Exclusions use their own subfolder as described below.
Both optional optimization exporters also accept the parsed metadata, preserve
specimen identity in CSV names and honor exclusions. Multi-source exports prefix
each CSV name with its source label to avoid collisions. Their manifests preserve
source paths and labels. Filename-mode exports go
under the analysis output in `optimization_90deg/` or `optimization_45deg/`.

Set `INPUT_MODE = "excel"` to use the original workbook input. Its path examples
and instructions remain in the notebook as a reference. The command-line
`scripts/run_analysis.py` continues to use Excel input.

### Curves that fail preprocessing

Notebook Step 2 defaults to `PREPROCESS_ON_ERROR = "skip"`: it processes each
curve independently and saves `preprocessing_report.csv` with a success/failure
status and error message for every attempt. A failure no longer stops the other
curves. Failed curves are absent from analysis plots and fits, but remain in
the results table with `preprocessing_status = "failed"`, the reason, and blank
fit parameters. Manually excluded curves are omitted from filtered results.

The contact threshold and correction rules are unchanged. Set
`PREPROCESS_ON_ERROR = "raise"` to stop on the first failure. If no curve succeeds,
the notebook stops after saving the report. Rerun preprocessing and both fitting
steps before saving after a change. The command-line pipeline keeps strict
preprocessing behavior by default.

### Loading-only or otherwise incomplete mono curves

The two-baseline drift correction is used only when the file contains loading,
at least 3 subsequent unloading points (`segm 3`), and at least 15 trailing
retract points (`segm 4`) for the post-test baseline. Otherwise, mono preprocessing
uses contact zeroing alone. The measured terminal loading force is never used as
a post-unloading zero-force baseline for these incomplete curves.

Incomplete curves remain in the analysis and both Hertz fits use their loading
data (`segm 1`). Plots mark them `[incomplete; no drift correction]`. The report
and result table include `mono_complete`, `mono_incomplete_reason`,
`drift_correction_applied`, and `preprocessing_method`. Incompleteness itself is
not a failure or an exclusion; missing contact or unsuitable fitting data may
still cause failure. Review fit quality as usual. SR preprocessing is unchanged.

### p50 contact-point limits

The p50 Hertz method uses loads >= 50% of the loading peak, while its contact
point is constrained relative to the preprocessed contact zero. Configure
`P50_CP_BOUNDS_UM` in `config.py` (default `(-20.0, 20.0)` µm). This replaces the
old lower limit tied to the beginning of the high-load subset. These are working
limits, not a measurement of contact uncertainty. The upper limit is also capped
just before the first high-load depth so the fitted model has positive indentation.

Boundary solutions emit a warning, show `[cp bound]` in plot legends and save
`cp_at_bound_p50`, `cp_lower_bound_um_p50`, and `cp_upper_bound_um_p50` in the
results. Review such solutions rather than interpreting an improved R² alone as
proof of a valid contact point. The moving method and plotting coordinates are
unchanged. Rerun the notebook setup/selection and subsequent analysis after
changing these settings.

## Excel reference workflow

For the original Excel workflow, the repository's `data/` directory can contain
the inputs below. Filename-mode inputs can stay in their original folders and do
not need these Excel files.

```
data/
├── raw/                          # your raw Bioindenter .TXT files (one per sample)
├── sample_groups.xlsx            # the metadata sheet the pipeline reads (you fill this in)
└── sample_groups_template.xlsx   # a blank example showing the required format
```

---

## To run the Excel-based command-line pipeline (3 steps)

1. **Drop your raw files** into `data/raw/` (one `.TXT` per sample).
2. **Copy** `sample_groups_template.xlsx` -> `sample_groups.xlsx` and **fill in one row per file**
   (see the columns below).
3. From the repository root, run:

   ```
   python scripts/run_analysis.py
   ```

   No path changes are needed — `config.py` already points at this `data/` folder.
   (Only edit `SAMPLE_SHEET` / `RAW_DATA_DIR` in `config.py` if your data lives elsewhere.)

---

## `sample_groups.xlsx` — the columns

| column        | required | type    | allowed values / example              | notes |
| ------------- | -------- | ------- | ------------------------------------- | ----- |
| `file_name`   | yes      | text    | `sample_01.TXT`                       | must match a file inside `data/raw/` exactly |
| `sample_id`   | yes      | integer | `1`, `2`, `3` ...                     | unique per sample; the key used for the results |
| `treatment`   | yes      | text    | `Native`, `Crosslinked`, `Degraded`, `Degraded_after_crosslinked`        | use these four treatment names consistently |
| `test_type`   | yes      | text    | **`mono`** or **`stress_relaxation`** | picks the analysis: Hertz (mono) or Prony (SR) |
| `Group`       | yes      | text    | `Group A Native Mono`                 | grouping label — see the pairing rule below |

Any extra columns you add (notes, dates, status, ...) are **kept** and carried through to the
results. Optional `batch` and `sample_name` fields are also used for source
styling and specimen labels when supplied.

## Comparing multiple experimental batches using Excel (reference)

For the normal filename workflow, use `FILENAME_SOURCES` above instead. The
following joint-workbook method remains available for legacy Excel input.

Keep the original raw files and source sheets in place. Create a separate joint
`sample_groups.xlsx` with one row per measurement and paths relative to a common
`CIA_RAW_DATA_DIR`. File names may include subdirectories, for example
`20261022/Native/Measurement_1_Sample_A_native_mono_1.TXT`.

- Assign globally unique integer `sample_id` values. Duplicate IDs or file names
  are rejected, because fit results are joined using `sample_id`.
- Keep `original_sample_id`, `original_group`, and `source_sheet` for traceability.
- Add an optional `batch` column (for example `20261022`). Plots use a consistent
  line style per batch (four styles cycle). Legends show specimen codes when
  available and otherwise fall back to the batch label.
- Prefix `Group` with the batch so each batch retains its own raw/corrected plot.
- Keep treatment names unchanged. Treatment comparisons pool batches, while
  additional Native comparisons show batches separately for each test type.

The pipeline recalculates fits using the current `config.py` settings and writes
them into the joint sheet. Source sheets are untouched. Curves are overlays;
they do not establish statistical significance or matched biological samples.

For the 20261022 and 20261026 datasets, the joint directory is
`/Users/xkk/Desktop/ExprimentResultsRawDataIndentation /20261022_26/combined_analysis`.
Run its launcher with the Python environment containing the project dependencies:

```bash
/opt/anaconda3/bin/python "/Users/xkk/Desktop/ExprimentResultsRawDataIndentation /20261022_26/combined_analysis/run_combined.py"
```

Results go into `combined_analysis/Analysis_Output/`; fitted parameters are
written to `combined_analysis/sample_groups.xlsx`.

For future batches, `scripts/combine_batches.py` validates source files and emits
a JSON manifest for spreadsheet export. Supply `--root COMMON_RAW_ROOT`,
`--output NEW_MANIFEST.json`, and one `--batch LABEL SHEET RAW_DIR` per batch.
It assigns new IDs in source order and omits previous fit columns. Keep the
batch list/order stable when regenerating to preserve the assigned IDs.

## Excluding curves in the notebook

In `notebooks/analysis.ipynb`, run the setup and load cells, then edit Step **1a**:

```python
EXCLUDE_SAMPLE_IDS = [17, 25]  # current sheet's sample_id, not original_sample_id
EXCLUDE_FILE_NAMES = []       # alternatively, exact file_name paths from the sheet
EXCLUSION_NOTE = "Reason for excluding these curves"
```

Both lists default to empty. A curve matching either list is excluded from
preprocessing, comparison plots, and fits. Rerun Step 1a and all analysis cells
below it after changing the selection. Clear the lists to restore every curve.

Filtered runs save figures and `analysis_results.xlsx` under
`Analysis_Output/excluded_<selection>/`. The results sheet contains only included
samples; `excluded_samples.csv` and `included_samples.csv` record the selection.
The input workbook and raw files are preserved. Unknown IDs/paths and excluding
every curve raise errors. The save cell also checks that both fitting steps were
rerun for the current selection.

Optional optimization exporters honor exclusions by resolved raw-file path when
Step 1a has run in the same kernel. Their dataset roots must point to those same
files. Matching exclusions use a separate export subfolder to avoid mixing older
unfiltered CSVs into the filtered run. Notebook exclusions do not affect the
separate `scripts/run_analysis.py` command.

## Treatment comparisons and the `Group` column

Use exactly these treatment names (case-sensitive): `Native`, `Crosslinked`,
`Degraded`, `Degraded_after_crosslinked`. Unknown names raise an error.

For each `test_type` (`mono` and `stress_relaxation`) separately, the pipeline produces:

1. Native vs. Crosslinked.
2. Native vs. Degraded.
3. Native vs. Degraded_after_crosslinked.
4. Degraded vs. Degraded_after_crosslinked.
5. Crosslinked vs. Degraded_after_crosslinked.
6. All four treatments on one figure.

These comparisons apply to corrected curves, mono Hertz fits (both methods), and
stress-relaxation Prony fits. Treatment colors stay consistent between figures.
If a required treatment is absent, that comparison is skipped with a warning;
individual samples are still fitted. These are curve overlays, not statistical tests
or matched-specimen comparisons.

`Group` remains the label for per-group raw-vs-corrected plots, for example
`Native Mono` or `Crosslinked Stress Relaxation`. Each Group must contain only
one treatment and one test type. Comparisons use the `treatment` and `test_type`
columns, pooling all groups with the same combination; Group names need not match.

The `sample_groups_template.xlsx` contains eight example rows: all four treatments
for each test type. Replace the example file names and sample IDs with your own;
add one row per raw file and keep the treatment names exactly as shown.

---

## The raw `.TXT` format

One file per sample, as exported by the Bioindenter:

- A header block, ending with a line that reads exactly `Measured values`.
- After that line, **tab-separated** columns in this order: `time, displ, load, ref_load, segm`.
- **Units:** `displ` in um, `load` in mN, `time` in s.
- **`segm`** is the instrument's test-phase label:
  - **mono:** `1` = loading ramp, `2` = hold, `3` = unloading, `4` = retract.
  - **stress-relaxation:** the pipeline keeps segments `[5, 6, 7, 8]` (`TARGET_SEGS_SR` in `config.py`).

The Hertz fit uses only the loading ramp (`segm 1`); the stress-relaxation fit uses the
relaxation part of segments 5-8.
