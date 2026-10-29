"""Read the sample-metadata sheet and index the raw files by group / sample."""
import os
import re
from pathlib import Path

import pandas as pd

TREATMENTS = ("Native", "Crosslinked", "Degraded", "Degraded_after_crosslinked")

_FILENAME_PATTERN = re.compile(
    r"Measurement_(?P<measurement>\d+)_Sample_(?P<specimen>[a-z0-9]+)_"
    r"(?P<status>native|crosslinked|degraded|degraded_after_crosslinking|degraded_after_crosslinked)_"
    r"(?P<test_type>mono|stress_relaxation)_(?P<curve_number>\d+)\.txt", re.IGNORECASE)
_STATUS_TREATMENTS = {
    "native": "Native", "crosslinked": "Crosslinked", "degraded": "Degraded",
    "degraded_after_crosslinking": "Degraded_after_crosslinked",
    "degraded_after_crosslinked": "Degraded_after_crosslinked",
}


def _sample_code(sample_name, file_name):
    """Compact specimen identity for legends, with a filename fallback for Excel input."""
    name = "" if pd.isna(sample_name) else str(sample_name).strip()
    for candidate in (name, Path(file_name).name):
        match = re.match(r"^Measurement_(\d+)_Sample_([a-z0-9]+)(?:_|$)", candidate, re.IGNORECASE)
        if match:
            return f"M{int(match[1])}S{match[2].upper()}"
    return name


def metadata_from_filenames(raw_data_dir, *, batch="", recursive=False):
    """Read metadata from raw file names; never create or read an Excel sheet.

    Measurement_3_Sample_A_native_mono_1.TXT yields specimen name
    Measurement_3_Sample_A, Native treatment, mono test and curve_number=1.
    Analysis IDs are unique sequential integers in deterministic natural order;
    curve numbers need not be unique. Use relative paths for exclusions that must
    remain stable if files are later added or removed.
    """
    root = Path(raw_data_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {root}")
    paths = root.rglob("*") if recursive else root.iterdir()
    files = sorted(p for p in paths if p.is_file() and p.suffix.lower() == ".txt")
    if not files:
        raise ValueError(f"No .TXT curve files found in {root}")
    rows, invalid = [], []
    for path in files:
        match = _FILENAME_PATTERN.fullmatch(path.name)
        if match is None:
            invalid.append(str(path.relative_to(root)))
            continue
        info = match.groupdict()
        measurement = int(info["measurement"])
        specimen = info["specimen"].upper()
        sample_name = f"Measurement_{measurement}_Sample_{specimen}"
        treatment = _STATUS_TREATMENTS[info["status"].lower()]
        test_type = info["test_type"].lower()
        group = f"{sample_name} {treatment} {test_type}"
        rows.append({"file_name": str(path.relative_to(root)), "sample_name": sample_name,
                     "measurement": measurement, "specimen": specimen,
                     "status": info["status"].lower(), "treatment": treatment,
                     "test_type": test_type, "Group": group, "batch": str(batch),
                     "curve_number": int(info["curve_number"])})
    if invalid:
        raise ValueError("Cannot parse .TXT filenames (no curves were loaded):\n" + "\n".join(invalid))
    rows.sort(key=lambda r: (r["measurement"], r["specimen"], r["curve_number"], r["file_name"]))
    for sample_id, row in enumerate(rows, 1):
        row["sample_id"] = sample_id
    columns = ["file_name", "sample_id", "sample_name", "treatment", "test_type", "Group",
               "batch", "measurement", "specimen", "status", "curve_number"]
    return pd.DataFrame(rows, columns=columns)


def metadata_from_filename_sources(sources):
    """Combine filename metadata from one or more explicitly selected folders.

    Each source has path, optional batch/label, and recursive (default False).
    Return (metadata, common_root), keeping provenance and unique global IDs.
    Multi-source Group labels include source identity to avoid merging specimens
    that happen to share the same measurement/sample name across folders.
    """
    sources = list(sources)
    if not sources:
        raise ValueError("Provide at least one filename source")
    roots = [Path(source["path"]).expanduser().resolve() for source in sources]
    common_root = Path(os.path.commonpath([str(root) for root in roots]))
    frames, seen_paths, seen_labels = [], set(), set()
    for source, root in zip(sources, roots):
        label = source.get("label", re.sub(r"[^a-zA-Z0-9_-]+", "_", root.name))
        if not isinstance(label, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", label):
            raise ValueError("Source labels must use letters, numbers, underscores or hyphens")
        if label in seen_labels:
            raise ValueError(f"Duplicate source label {label!r}; assign unique labels to each folder")
        seen_labels.add(label)
        try:
            frame = metadata_from_filenames(root, batch=source.get("batch", ""),
                                             recursive=source.get("recursive", False))
        except (ValueError, FileNotFoundError) as error:
            raise ValueError(f"Filename source {label!r} ({root}): {error}") from error
        frame["source_label"] = label
        frame["source_root"] = str(root)
        frame["source_file_name"] = frame["file_name"]
        actual_paths = [(root / name).resolve() for name in frame["file_name"]]
        for path in actual_paths:
            if path in seen_paths:
                raise ValueError(f"Raw file selected more than once (overlapping sources or symlinks): {path}")
            seen_paths.add(path)
        frame["source_path"] = [str(path) for path in actual_paths]
        frame["file_name"] = [os.path.relpath(path, common_root) for path in actual_paths]
        if len(sources) > 1:
            frame["Group"] = label + " " + frame["Group"]
        frames.append(frame)
    metadata = pd.concat(frames, ignore_index=True)
    metadata["sample_id"] = range(1, len(metadata) + 1)
    return metadata, common_root


class SampleIndex:
    """Index of all raw files, built from the metadata sheet.

    The sheet must have columns: ``file_name, sample_id, treatment, test_type, Group``
    (``test_type`` is ``mono`` or ``stress_relaxation``; ``Group`` is the grouping label).
    """

    def __init__(self, sample_sheet_path, raw_data_dir):
        df = pd.read_excel(sample_sheet_path)
        self._initialize(df, raw_data_dir)

    @classmethod
    def from_dataframe(cls, metadata, raw_data_dir):
        index = cls.__new__(cls)
        index._initialize(metadata, raw_data_dir)
        return index

    @classmethod
    def from_filenames(cls, raw_data_dir, *, batch="", recursive=False):
        return cls.from_dataframe(metadata_from_filenames(
            raw_data_dir, batch=batch, recursive=recursive), raw_data_dir)

    @classmethod
    def from_filename_sources(cls, sources):
        metadata, common_root = metadata_from_filename_sources(sources)
        return cls.from_dataframe(metadata, common_root)

    def _initialize(self, df, raw_data_dir):
        df = df.copy()
        for c in ["file_name", "treatment", "test_type", "Group"]:
            df[c] = df[c].astype(str).str.strip()
        # collapse any internal double spaces (a common typo) so grouping / pairing is robust
        for c in ["treatment", "test_type", "Group"]:
            df[c] = df[c].str.replace(r"\s+", " ", regex=True)
        df["sample_id"] = df["sample_id"].astype(int)
        if df["sample_id"].duplicated().any():
            raise ValueError("sample_id must be unique across all batches")
        if df["file_name"].duplicated().any():
            raise ValueError("file_name must be unique across all batches")
        df["batch"] = df["batch"].fillna("").astype(str).str.strip() if "batch" in df else ""
        unknown = sorted(set(df["treatment"]) - set(TREATMENTS))
        if unknown:
            raise ValueError(f"Unknown treatment(s): {unknown}. Expected: {TREATMENTS}")
        for group, rows in df.groupby("Group"):
            if rows["test_type"].nunique() != 1 or rows["treatment"].nunique() != 1:
                raise ValueError(f"Group {group!r} must have one treatment and one test_type")
        self.sample_df = df
        self.raw_data_dir = raw_data_dir
        self.excluded_df = df.iloc[:0].copy()
        self.preprocessing_report = pd.DataFrame()
        self._preprocessing_by_id = {}

        # Metadata keyed by file name ('group' holds the 'Group' column)
        self._by_name = {
            row.file_name: {"sample_id": row.sample_id, "treatment": row.treatment,
                            "test_type": row.test_type, "group": row.Group, "batch": row.batch}
            for row in df.itertuples(index=False)
        }
        for row in df.itertuples(index=False):
            self._by_name[row.file_name]["sample_code"] = _sample_code(
                getattr(row, "sample_name", ""), row.file_name)

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

    def excluding(self, sample_ids=(), file_names=()):
        """Return a fresh index; exclusions never change the original sheet/index.

        File names must match the sheet's relative paths. Unknown selections and
        an empty remaining dataset raise errors to catch typos before analysis.
        Always call on the full index when editing a notebook's exclusion list.
        """
        sample_ids, file_names = set(sample_ids), set(file_names)
        unknown_ids = sample_ids - set(self.sample_df["sample_id"])
        unknown_files = file_names - set(self.sample_df["file_name"])
        if unknown_ids or unknown_files:
            raise ValueError(f"Unknown exclusions: sample_ids={sorted(unknown_ids)}, "
                             f"file_names={sorted(unknown_files)}")
        mask = (self.sample_df["sample_id"].isin(sample_ids) |
                self.sample_df["file_name"].isin(file_names))
        if mask.all():
            raise ValueError("Exclusions would remove all samples. Keep at least one curve.")
        selected = SampleIndex.__new__(SampleIndex)
        selected._initialize(self.sample_df.loc[~mask], self.raw_data_dir)
        selected.excluded_df = self.sample_df.loc[mask].copy()
        return selected

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
    def batch(self, path):      return self._info(path).get("batch", "")

    def line_style(self, path):
        batches = list(dict.fromkeys(self.sample_df["batch"]))
        return ("-", "--", "-.", ":")[batches.index(self.batch(path)) % 4]

    def sample_label(self, path):
        label = f"#{self.sample_id(path)}"
        sample_code = self._info(path).get("sample_code", "")
        if sample_code:
            label += f" ({sample_code})"
        elif self.batch(path):
            label = f"{label} [{self.batch(path)}]"
        complete = self.preprocessing_info(path).get("mono_complete")
        if pd.notna(complete) and complete == False:
            label += " [incomplete; no drift correction]"
        return label

    def set_preprocessing_report(self, report):
        self.preprocessing_report = report.copy()
        self._preprocessing_by_id = report.set_index("sample_id").to_dict("index")

    def preprocessing_info(self, path):
        return self._preprocessing_by_id.get(self.sample_id(path), {})


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


def batch_comparisons(index):
    """Compare Native across batches for each test type, without implying pairing."""
    comparisons = []
    for test_type in ("mono", "stress_relaxation"):
        files = {}
        for path in index.files:
            if index.treatment(path) == "Native" and index.test_type(path) == test_type and index.batch(path):
                files.setdefault(index.batch(path), []).append(path)
        if len(files) > 1:
            comparisons.append({"name": f"{test_type}: Native across batches",
                                "type": test_type, "treatments": tuple(files),
                                "files": files, "batch_comparison": True,
                                "filename": f"Comparison_{test_type}_Native_batches.png"})
    return comparisons
