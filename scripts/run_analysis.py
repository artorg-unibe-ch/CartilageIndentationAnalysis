"""Run the full cartilage indentation analysis pipeline.

Edit ``config.py`` (paths + parameters) first, then run from the repository root:

    python scripts/run_analysis.py

Steps: load metadata -> preprocess (drift correction + contact zeroing) -> plots ->
Hertz fits (mono) -> Prony fit (stress-relaxation) -> write parameters to the sheet.
"""
import os
import sys

# Make the repository root importable (so `config` and `cartilage_indentation` resolve).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as cfg
from cartilage_indentation.dataset import SampleIndex, native_uv_pairs
from cartilage_indentation.preprocessing import preprocess_all
from cartilage_indentation.hertz import get_loading
from cartilage_indentation import plotting
from cartilage_indentation.results import save_results


def main():
    for d in (cfg.DIR_RAW_PLOTS, cfg.DIR_RAW_VS_CORR, cfg.DIR_COMPARISON, cfg.DIR_MONO_FIT):
        os.makedirs(d, exist_ok=True)

    # 1. Load metadata and group the raw files
    index = SampleIndex(cfg.SAMPLE_SHEET, cfg.RAW_DATA_DIR)
    pairs = native_uv_pairs(index)
    print(f"Loaded {len(index.files)} files in {len(index.group_order)} groups "
          f"({len(index.subgroup_mono)} mono, {len(index.subgroup_sr)} stress-relaxation).")

    # 2. Preprocess: drift correction (mono) + contact-threshold zeroing
    mono_data, sr_data = preprocess_all(index, cfg)

    # 3. Overview plots
    plotting.plot_raw_vs_corrected(index, mono_data, sr_data, cfg.DIR_RAW_VS_CORR)
    plotting.plot_comparison_native_uv(index, pairs, mono_data, sr_data, cfg.DIR_COMPARISON)

    # 4. Mono Hertz fits (loading curve; two contact-point methods)
    mono_loading = {}
    for g in index.subgroup_mono:
        for path in index.subgrouped_files[g]:
            df = mono_data.get(path)
            if df is not None and not df.empty:
                mono_loading[path] = get_loading(df)

    res_moving = plotting.fit_and_plot_mono(index, pairs, mono_loading, "moving",
                                            "Way2 Loading Moving", cfg.DIR_MONO_FIT,
                                            cfg.PROBE_RADIUS, cfg.POISSON_RATIO)
    res_p50 = plotting.fit_and_plot_mono(index, pairs, mono_loading, "p50",
                                         "Way3 Loading p50", cfg.DIR_MONO_FIT,
                                         cfg.PROBE_RADIUS, cfg.POISSON_RATIO)

    # 5. Stress-relaxation 1-term Prony fits
    prony_df = plotting.fit_and_plot_sr(index, pairs, sr_data, cfg.DIR_COMPARISON,
                                        cfg.SR_FIT_MAX_TIME)

    # 6. Write all fit parameters back into the metadata sheet
    save_results(cfg.SAMPLE_SHEET, {"moving": res_moving, "p50": res_p50}, prony_df)

    print(f"Done. Figures -> {cfg.OUTPUT_ROOT}")
    print(f"Fit parameters appended to {os.path.basename(cfg.SAMPLE_SHEET)}")


if __name__ == "__main__":
    main()
