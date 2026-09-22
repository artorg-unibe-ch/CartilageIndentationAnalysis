"""Configuration.

By default the pipeline reads the data bundled in this repo's data/ folder,
so after `git clone` it runs as-is:

    python scripts/run_analysis.py

------------------------------------------------------------------------------
Run on data in a SEPARATE folder (no code changes, nothing copied into the repo)
------------------------------------------------------------------------------
Arrange the external folder like this:

    my_new_dataset/
        raw/                     <- your .TXT files
        sample_groups.xlsx       <- the metadata sheet (copy data/sample_groups_template.xlsx)

Then point the pipeline at it with an environment variable BEFORE running:

    # macOS / Linux
    export CIA_DATA_ROOT="/Users/you/path/to/my_new_dataset"
    python scripts/run_analysis.py

    # Windows PowerShell
    $env:CIA_DATA_ROOT="C:\\path\\to\\my_new_dataset"
    python scripts\\run_analysis.py

Results are written to  <CIA_DATA_ROOT>/Analysis_Output  (the repo stays untouched).

For finer control you can instead set CIA_SAMPLE_SHEET / CIA_RAW_DATA_DIR /
CIA_OUTPUT_ROOT individually. See notebooks/analysis.ipynb for how to do the
same thing from inside the notebook.
"""
import os

# Repository root (the folder containing this file)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Where the data lives.
#   default            -> the data/ folder bundled in this repository
#   CIA_DATA_ROOT set  -> that external folder (must contain raw/ + sample_groups.xlsx)
# ---------------------------------------------------------------------------
_EXTERNAL   = "CIA_DATA_ROOT" in os.environ
DATA_ROOT   = os.environ.get("CIA_DATA_ROOT", os.path.join(REPO_ROOT, "data"))

# Input paths (individual overrides win over DATA_ROOT)
SAMPLE_SHEET = os.environ.get("CIA_SAMPLE_SHEET", os.path.join(DATA_ROOT, "sample_groups.xlsx"))
RAW_DATA_DIR = os.environ.get("CIA_RAW_DATA_DIR", os.path.join(DATA_ROOT, "raw"))

# ---------------------------------------------------------------------------
# Output folders (created automatically; git-ignored)
#   default            -> Analysis_Output/ next to the code (repo data)
#   external data      -> Analysis_Output/ inside the external data folder
# ---------------------------------------------------------------------------
_OUTPUT_BASE    = DATA_ROOT if _EXTERNAL else REPO_ROOT
OUTPUT_ROOT     = os.environ.get("CIA_OUTPUT_ROOT", os.path.join(_OUTPUT_BASE, "Analysis_Output"))
DIR_RAW_PLOTS   = os.path.join(OUTPUT_ROOT, "Raw Data Plots")
DIR_RAW_VS_CORR = os.path.join(OUTPUT_ROOT, "Raw vs Corrected Plots")
DIR_COMPARISON  = os.path.join(OUTPUT_ROOT, "Comparison Native vs. UV Plots")
DIR_MONO_FIT    = os.path.join(OUTPUT_ROOT, "Mono Hertz Fit Comparison")

# ---------------------------------------------------------------------------
# Analysis parameters
# ---------------------------------------------------------------------------
PROBE_RADIUS   = 500.0            # spherical indenter radius [µm]
POISSON_RATIO  = 0.25             # sample Poisson ratio
TARGET_SEGS_SR = [5, 6, 7, 8]     # instrument segments kept for stress-relaxation files

# Contact detection (first row where load stays above the threshold)
CONTACT_COLUMN     = "load"
CONTACT_THRESHOLD  = 6.0          # mN
CONTACT_MIN_CONSEC = 3            # consecutive rows above threshold

# Stress-relaxation Prony fit window: from the load peak to this time [s]
SR_FIT_MAX_TIME = 120.0
