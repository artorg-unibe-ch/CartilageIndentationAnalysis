# `data/` — inputs for the pipeline

This folder holds everything the analysis reads. **You do not need to edit any code or set
any absolute paths** — just put your files here in the right shape and run.

```
data/
├── raw/                          # your raw Bioindenter .TXT files (one per sample)
├── sample_groups.xlsx            # the metadata sheet the pipeline reads (you fill this in)
└── sample_groups_template.xlsx   # a blank example showing the required format
```

---

## To run the pipeline on your own data (3 steps)

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
results — the pipeline only reads the five columns above.

## Comparing multiple experimental batches

Keep the original raw files and source sheets in place. Create a separate joint
`sample_groups.xlsx` with one row per measurement and paths relative to a common
`CIA_RAW_DATA_DIR`. File names may include subdirectories, for example
`20261022/Native/20261022# 1.TXT`.

- Assign globally unique integer `sample_id` values. Duplicate IDs or file names
  are rejected, because fit results are joined using `sample_id`.
- Keep `original_sample_id`, `original_group`, and `source_sheet` for traceability.
- Add an optional `batch` column (for example `20261022`). Plots show the batch in
  legends and use a consistent line style for each batch (four styles cycle).
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
