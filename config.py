"""User configuration — edit the paths and parameters for your machine, then run
`python scripts/run_analysis.py`.
"""
import os

# ---------------------------------------------------------------------------
# Input paths
# ---------------------------------------------------------------------------
START_DIR    = r"/Users/xkk/Desktop/Experiments_optimization/20260609 Crosslinking test 2_Riboflavin Part 1_2_Sigma"
SAMPLE_SHEET = os.path.join(START_DIR, "sample_groups.xlsx")
RAW_DATA_DIR = os.path.join(START_DIR, "20260609_Indentor_Raw Data")

# ---------------------------------------------------------------------------
# Output folders (created automatically under a writable root)
# ---------------------------------------------------------------------------
OUTPUT_ROOT     = os.path.join(START_DIR, "Analysis_Output")
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
