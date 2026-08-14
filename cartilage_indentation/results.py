"""Write the fit parameters back into the sample-metadata sheet."""
import pandas as pd

# Columns produced by the pipeline (dropped and re-added on every run, so re-running
# never duplicates columns; all other columns in the sheet are preserved).
FIT_COLS = ["Es_moving", "cp_moving", "r2_moving", "Es_p50", "cp_p50", "r2_p50",
            "g1", "ge", "tau1_s", "F0_mN", "r2_prony"]


def save_results(sample_sheet_path, mono_results, prony_df):
    """Append fit parameters to the metadata sheet (one row per sample).

    ``mono_results`` maps a method key to its results DataFrame, e.g.
    ``{"moving": df, "p50": df}`` (each with columns ``sample_id, Es, cp, r2``).
    ``prony_df`` has columns ``sample_id, g1, ge, tau1_s, F0_mN, r2_prony``.
    """
    results = pd.read_excel(sample_sheet_path)
    results = results.drop(columns=[c for c in FIT_COLS if c in results.columns])
    results["sample_id"] = results["sample_id"].astype(int)

    for method_key, res in mono_results.items():
        if res is None or res.empty:
            continue
        cols = res[["sample_id", "Es", "cp", "r2"]].rename(columns={
            "Es": f"Es_{method_key}", "cp": f"cp_{method_key}", "r2": f"r2_{method_key}"})
        results = results.merge(cols, on="sample_id", how="left")

    if prony_df is not None and not prony_df.empty:
        results = results.merge(
            prony_df[["sample_id", "g1", "ge", "tau1_s", "F0_mN", "r2_prony"]],
            on="sample_id", how="left")

    results.to_excel(sample_sheet_path, index=False)
    return results
