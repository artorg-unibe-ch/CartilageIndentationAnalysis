"""Read the sample-metadata sheet and index the raw files by group / sample."""
import os

import pandas as pd


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
        return self._by_name.get(
            os.path.basename(path),
            {"sample_id": -1, "treatment": "unknown", "test_type": "unknown", "group": "unknown"},
        )

    def sample_id(self, path):  return self._info(path)["sample_id"]
    def group(self, path):      return self._info(path)["group"]
    def treatment(self, path):  return self._info(path)["treatment"]
    def test_type(self, path):  return self._info(path)["test_type"]


def native_uv_pairs(index):
    """Build Native-vs-UV comparison pairs from the group names.

    Every ``Native`` group is paired with its ``UV`` counterpart (same base name and
    test_type), so the pairing stays in sync if the sheet's groups change.
    """
    pairs = []
    for g in index.group_order:
        if "Native" not in g:
            continue
        uv_key = g.replace("Native", "UV")
        if uv_key not in index.subgrouped_files:
            continue
        name = g.replace(" Native", "")
        safe = "".join(c for c in name if c.isalnum() or c == " ").strip().replace(" ", "_")
        pairs.append({
            "name": name,
            "type": index.group_ttype[g],
            "native_key": g,
            "uv_key": uv_key,
            "filename": f"Comparison_{safe}_Native_vs_UV.png",
        })
    return pairs
