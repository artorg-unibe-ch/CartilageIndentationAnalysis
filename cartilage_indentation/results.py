"""Write the fit parameters back into the sample-metadata sheet."""
import pandas as pd

# Columns produced by the pipeline (dropped and re-added on every run, so re-running
# never duplicates columns; all other columns in the sheet are preserved).
FIT_COLS = ["Es_moving", "cp_moving", "r2_moving", "Es_p50", "cp_p50", "r2_p50",
            "g1", "ge", "tau1_s", "F0_mN", "r2_prony",
            "cp_at_bound_p50", "cp_lower_bound_um_p50", "cp_upper_bound_um_p50"]
PREPROCESS_COLS = ["preprocessing_status", "preprocessing_error"]
MONO_INFO_COLS = ["mono_complete", "mono_incomplete_reason", "drift_correction_applied",
                  "preprocessing_method"]


def save_results(sample_sheet_path, mono_results, prony_df, *, output_path=None,
                 included_sample_ids=None, metadata=None, preprocessing_report=None):
    """Append fit parameters to the metadata sheet (one row per sample).

    ``mono_results`` maps a method key to its results DataFrame, e.g.
    ``{"moving": df, "p50": df}`` (each with columns ``sample_id, Es, cp, r2``).
    ``prony_df`` has columns ``sample_id, g1, ge, tau1_s, F0_mN, r2_prony``.
    Set ``output_path`` and ``included_sample_ids`` to save a filtered analysis
    separately. Filtering requires a different output path to protect the source.
    Filename input can pass ``metadata`` instead of reading a sheet, together
    with an explicit ``output_path``. The metadata DataFrame is not modified.
    """
    if metadata is not None:
        if output_path is None:
            raise ValueError("In-memory metadata requires an output_path")
        results = metadata.copy()
    else:
        results = pd.read_excel(sample_sheet_path)
    results = results.drop(columns=[c for c in FIT_COLS + PREPROCESS_COLS + MONO_INFO_COLS if c in results.columns])
    results["sample_id"] = results["sample_id"].astype(int)
    if included_sample_ids is not None:
        from pathlib import Path
        if output_path is None or (sample_sheet_path is not None and
                Path(output_path).resolve() == Path(sample_sheet_path).resolve()):
            raise ValueError("Filtered results require a separate output_path")
        included_sample_ids = set(included_sample_ids)
        unknown = included_sample_ids - set(results["sample_id"])
        if unknown:
            raise ValueError(f"Unknown included sample IDs: {sorted(unknown)}")
        results = results.loc[results["sample_id"].isin(included_sample_ids)].copy()

    for method_key, res in mono_results.items():
        if res is None or res.empty:
            continue
        optional = [c for c in ("cp_at_bound", "cp_lower_bound_um", "cp_upper_bound_um") if c in res]
        cols = res[["sample_id", "Es", "cp", "r2"] + optional].rename(columns={
            "Es": f"Es_{method_key}", "cp": f"cp_{method_key}", "r2": f"r2_{method_key}",
            **{c: f"{c}_{method_key}" for c in optional}})
        results = results.merge(cols, on="sample_id", how="left", validate="one_to_one")
        flag_column = f"cp_at_bound_{method_key}"
        if flag_column in results:
            results[flag_column] = results[flag_column].astype("boolean")

    if prony_df is not None and not prony_df.empty:
        results = results.merge(
            prony_df[["sample_id", "g1", "ge", "tau1_s", "F0_mN", "r2_prony"]],
            on="sample_id", how="left", validate="one_to_one")

    if preprocessing_report is not None:
        report = preprocessing_report[["sample_id"] + PREPROCESS_COLS +
                                      [c for c in MONO_INFO_COLS if c in preprocessing_report.columns]]
        if report["sample_id"].duplicated().any() or not set(results["sample_id"]).issubset(report["sample_id"]):
            raise ValueError("Preprocessing report must identify every result sample exactly once")
        if not report["preprocessing_status"].isin(["ok", "failed"]).all():
            raise ValueError("Invalid preprocessing status in report")
        results = results.merge(report, on="sample_id", how="left", validate="one_to_one")
        failed = results["preprocessing_status"].eq("failed")
        if failed.any():
            for column in (c for c in FIT_COLS if c in results.columns):
                results.loc[failed, column] = pd.NA if column == "cp_at_bound_p50" else float("nan")
    results.to_excel(output_path if output_path is not None else sample_sheet_path, index=False)
    return results


def save_fit_issues(results, output_path):
    """List missing fits and negative R² without excluding samples or imposing a cutoff."""
    issues = []
    for _, row in results.iterrows():
        methods = [("moving", "r2_moving"), ("p50", "r2_p50")] if row["test_type"] == "mono" else [("prony", "r2_prony")]
        for method, column in methods:
            r2 = row.get(column, float("nan"))
            if pd.isna(r2) or r2 < 0:
                issue = {key: row.get(key, "") for key in
                         ("sample_id", "batch", "original_sample_id", "file_name")}
                issue.update(method=method, status="missing_fit" if pd.isna(r2) else "negative_R2", R2=r2)
                issues.append(issue)
    columns = ["sample_id", "batch", "original_sample_id", "file_name", "method", "status", "R2"]
    pd.DataFrame(issues, columns=columns).to_csv(output_path, index=False)
    return len(issues)
