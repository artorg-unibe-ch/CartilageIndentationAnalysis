"""Reading raw Bioindenter files."""
import io

import pandas as pd


def load_raw_txt(path):
    """Read a Bioindenter ``.TXT`` file.

    The file has a header block terminated by a ``Measured values`` line, followed
    by tab-separated columns. Returns a DataFrame with columns
    ``[time, displ, load, ref_load, segm]`` (displacement in µm, load in mN, time in s).
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "Measured values")
    df = pd.read_csv(io.StringIO("".join(lines[start + 1:])), sep="\t", skip_blank_lines=True)
    df.columns = ["time", "displ", "load", "ref_load", "segm"]
    return df
