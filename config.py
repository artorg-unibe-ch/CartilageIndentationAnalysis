"""Configuration. You normally do NOT need to change the paths.

The pipeline reads the data bundled in this repo's data/ folder, so after `git clone`
it runs as-is:

    python scripts/run_analysis.py

To analyse YOUR OWN data (no code changes needed):
  1. put your raw .TXT files in   data/raw/
  2. fill in                      data/sample_groups.xlsx   (copy the template; see data/README.md)
  3. run                          python scripts/run_analysis.py

Only edit SAMPLE_SHEET / RAW_DATA_DIR below if your data lives somewhere other than data/.
"""
import os

# Repository root (the folder containing this file)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Input paths (data lives under data/ in the repository)
# ---------------------------------------------------------------------------
SAMPLE_SHEET = os.path.join(REPO_ROOT, "data", "sample_groups.xlsx")
RAW_DATA_DIR = os.path.join(REPO_ROOT, "data", "raw")

# ---------------------------------------------------------------------------
# Output folders (created automatically; git-ignored)
# ---------------------------------------------------------------------------
OUTPUT_ROOT     = os.path.join(REPO_ROOT, "Analysis_Output")
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
