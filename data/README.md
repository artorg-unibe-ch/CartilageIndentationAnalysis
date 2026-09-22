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
| `treatment`   | yes      | text    | `Group A Native`, `Group A UV`        | free text describing the sample |
| `test_type`   | yes      | text    | **`mono`** or **`stress_relaxation`** | picks the analysis: Hertz (mono) or Prony (SR) |
| `Group`       | yes      | text    | `Group A Native Mono`                 | grouping label — see the pairing rule below |

Any extra columns you add (notes, dates, status, ...) are **kept** and carried through to the
results — the pipeline only reads the five columns above.

---

## The `Group` column and Native-vs-UV pairing (read this!)

`Group` is a label **you invent**; the usual convention is `treatment` + `test_type`
(e.g. `Group A Native Mono`). It controls two things:

1. **Grouping** — samples with the same `Group` are plotted together.
2. **Native-vs-UV comparison** — the pipeline automatically pairs a `Native` group with its
   `UV` counterpart for the comparison figures.

**Pairing rule:** the two group names must be **identical except that one contains `Native`
and the other `UV`.** The code simply swaps the word `Native` -> `UV`:

```
"Group A Native Mono"              <->  "Group A UV Mono"                OK  pairs
"Group A Native Stress Relaxation" <->  "Group A UV Stress Relaxation"   OK  pairs
"Group A Native Mono"              <->  "Group A UV - mono"              NO  won't pair (names differ)
```

If a `Native` group has no exactly-matching `UV` group it simply gets no comparison plot —
and the run prints a warning telling you which group didn't match, so you can fix the name.

The template `sample_groups_template.xlsx` shows one valid Native/UV pair for both `mono`
and `stress_relaxation`; copy that pattern.

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
