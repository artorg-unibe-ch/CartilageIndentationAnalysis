"""Read the sample-metadata sheet and index the raw files by group / sample."""
import os

import pandas as pd

TREATMENTS = ("Native", "Crosslinked", "Degraded", "Degraded_after_crosslinked")


class SampleIndex:
    """Index of all raw files, built from the metadata sheet.

    The sheet must have columns: ``file_name, sample_id, treatment, test_type, Group``
    (``test_type`` is ``mono`` or ``stress_relaxation``; ``Group`` is the grouping label).
    """

    def __init__(self, sample_sheet_path, raw_data_dir):
        df = pd.read_excel(sample_sheet_path)
        for c in ["file_name", "treatment", "test_type", "Group"]:
            df[c] = df[c].astype(str).str.strip()
        # collapse any internal double spaces (a common typo) so grouping / pairing is robust
        for c in ["treatment", "test_type", "Group"]:
            df[c] = df[c].str.replace(r"\s+", " ", regex=True)
        df["sample_id"] = df["sample_id"].astype(int)
        unknown = sorted(set(df["treatment"]) - set(TREATMENTS))
        if unknown:
            raise ValueError(f"Unknown treatment(s): {unknown}. Expected: {TREATMENTS}")
        for group, rows in df.groupby("Group"):
            if rows["test_type"].nunique() != 1 or rows["treatment"].nunique() != 1:
                raise ValueError(f"Group {group!r} must have one treatment and one test_type")
        self.sample_df = df
        self.raw_data_dir = raw_data_dir

        # Metadata keyed by file name ('group' holds the 'Group' column)
        self._by_name = {
            row.file_name: {"sample_id": row.sample_id, "treatment": row.treatment,
                            "test_type": row.test_type, "group": row.Group}
            for row in df.itertuples(index=False)
        }

        # Group order (first appearance) + mono / stress-relaxation split
        self.group_order = list(dict.fromkeys(df["Group"]))
        self.group_ttype = dict(zip(df["Group"], df["test_type"]))
        self.subgroup_mono = [g for g in self.group_order if self.group_ttype[g] == "mono"]
        self.subgroup_sr = [g for g in self.group_order if self.group_ttype[g] == "stress_relaxation"]

        # File paths (order = sheet order) and grouping
        self.files = [os.path.join(raw_data_dir, fn) for fn in df["file_name"]]
        self.subgrouped_files = {
            g: [f for f in self.files if self.group(f) == g] for g in self.group_order
        }

    # -- per-file metadata lookups --------------------------------------------
    def _info(self, path):
        # file_name may include subdirectories relative to raw_data_dir.
        relative_name = os.path.relpath(path, self.raw_data_dir)
        return self._by_name.get(
            relative_name,
            {"sample_id": -1, "treatment": "unknown", "test_type": "unknown", "group": "unknown"},
        )

    def sample_id(self, path):  return self._info(path)["sample_id"]
    def group(self, path):      return self._info(path)["group"]
    def treatment(self, path):  return self._info(path)["treatment"]
    def test_type(self, path):  return self._info(path)["test_type"]


def treatment_comparisons(index):
    """Five pairwise comparisons and a four-treatment overlay per test type.

    Pool groups with the same treatment/test_type. Group labels do not encode
    matched specimens, and these overlays do not imply statistical pairing.
    """
    comparisons = []
    for test_type in ("mono", "stress_relaxation"):
        files = {t: [p for p in index.files
                     if index.test_type(p) == test_type and index.treatment(p) == t]
                 for t in TREATMENTS}
        if not any(files.values()):
            continue
        selections = [("Native", t) for t in TREATMENTS[1:]] + [
            ("Degraded", "Degraded_after_crosslinked"),
            ("Crosslinked", "Degraded_after_crosslinked"),
            TREATMENTS,
        ]
        for treatments in selections:
            missing = [t for t in treatments if not files[t]]
            label = " vs. ".join(treatments) if len(treatments) == 2 else "All four treatments"
            if missing:
                print(f"WARNING: skip {test_type} {label}: missing {', '.join(missing)}")
                continue
            suffix = "_vs_".join(treatments) if len(treatments) == 2 else "All_four_treatments"
            comparisons.append({"name": f"{test_type}: {label}", "type": test_type,
                                "treatments": treatments,
                                "files": {t: files[t] for t in treatments},
                                "filename": f"Comparison_{test_type}_{suffix}.png"})
    return comparisons
