"""Contact detection, zeroing and baseline-drift correction.

The old "zero at the first row" is unreliable because the first sample is not the true
contact point. Instead the contact point is detected as the first row where the load
stays above a threshold for a few consecutive rows.
"""
import os
import warnings

import numpy as np
import pandas as pd

from .io_utils import load_raw_txt

MONO_INFO_COLS = ["mono_complete", "mono_incomplete_reason", "drift_correction_applied",
                  "preprocessing_method"]


class MonoPreprocessingError(ValueError):
    """Keep the curve classification when contact detection subsequently fails."""
    def __init__(self, message, metadata):
        super().__init__(message)
        self.metadata = metadata


def mono_curve_metadata(df, post_n=15):
    """Check the recorded phases required by the two-baseline drift correction.

    Mono phases: 1 loading, 2 hold, 3 unloading, 4 retract. Require at least
    three unloading points after loading and post_n trailing retract points.
    A truncated curve remains eligible for loading-only Hertz fitting.
    """
    df = df.sort_values("time").reset_index(drop=True)
    segments = df["segm"].to_numpy()
    loading = np.flatnonzero(segments == 1)
    reasons = []
    if not len(loading):
        reasons.append("missing_loading")
    after_loading = segments[loading[-1] + 1:] if len(loading) else segments[:0]
    if np.count_nonzero(after_loading == 3) < 3:
        reasons.append("missing_or_truncated_unloading")
    tail_count = 0
    for segment in segments[::-1]:
        if segment != 4:
            break
        tail_count += 1
    unloading = np.flatnonzero(segments == 3)
    if (tail_count < post_n or not len(unloading) or
            len(segments) - tail_count <= unloading[-1]):
        reasons.append("missing_post_retraction_baseline")
    complete = not reasons
    return {"mono_complete": complete, "mono_incomplete_reason": "; ".join(reasons),
            "drift_correction_applied": False,
            "preprocessing_method": ("drift_correction_and_contact_zeroing" if complete
                                     else "contact_zeroing_only")}


def find_contact_start(df, column="load", threshold=6.0, min_consecutive=3):
    """Positional index of the first row where ``column`` stays above ``threshold``
    for ``min_consecutive`` consecutive rows (the contact point)."""
    vals = df[column].to_numpy()
    count = 0
    for i, v in enumerate(vals):
        if v > threshold:
            count += 1
            if count >= min_consecutive:
                return i - min_consecutive + 1          # first row of the stable run
        else:
            count = 0
    raise ValueError(f"No stable region above {threshold} for {min_consecutive} "
                     f"consecutive rows in column '{column}'.")


def zero_from_contact(df, column="load", threshold=6.0, min_consecutive=3):
    """Detect contact by load threshold, drop pre-contact rows, and add zeroed columns.

    ``time_zeroed`` / ``displ_zeroed`` start at 0 at the contact row; ``load_zeroed`` is
    referenced to the pre-contact baseline so that true zero force = 0. Offsets are
    stored in ``df.attrs``.
    """
    if df.empty:
        return df
    df = df.sort_values("time").reset_index(drop=True)
    start_idx = find_contact_start(df, column, threshold, min_consecutive)
    baseline = float(df[column].iloc[:start_idx].mean()) if start_idx > 0 else float(df[column].iloc[0])
    t0 = float(df["time"].iloc[start_idx])
    d0 = float(df["displ"].iloc[start_idx])
    out = df.iloc[start_idx:].reset_index(drop=True).copy()
    out["time_zeroed"]  = out["time"]  - t0
    out["displ_zeroed"] = out["displ"] - d0
    out["load_zeroed"]  = out["load"]  - baseline
    out.attrs.update(time_offset=t0, displ_offset=d0, load_offset=baseline,
                     contact_index=int(start_idx), load_threshold=threshold)
    return out


def correct_mono_drift(df, load_col="load", time_col="time", post_n=15,
                       threshold=6.0, min_consecutive=3):
    """Two-point linear baseline-drift correction for a slow mono indentation.

    The load should read ~0 both before contact and after full retraction; the linear
    trend between those two "should-be-zero" baselines is the instrumental drift:
    ``tan(alpha) = (F_post - F_pre) / (t_post - t_pre)``, and the correction is
    ``F_true(t) = F(t) - [F_pre + tan(alpha) * (t - t_pre)]`` (both baselines -> 0).
    Overwrites the load column; stores the drift rate in ``df.attrs``.
    """
    df = df.sort_values(time_col).reset_index(drop=True).copy()
    ci = find_contact_start(df, column=load_col, threshold=threshold, min_consecutive=min_consecutive)
    pre  = df.iloc[:ci] if ci > 0 else df.head(post_n)   # pre-contact baseline
    post = df.tail(post_n)                               # post-retract baseline (out of contact)
    F_pre,  t_pre  = float(pre[load_col].mean()),  float(pre[time_col].mean())
    F_post, t_post = float(post[load_col].mean()), float(post[time_col].mean())
    slope = (F_post - F_pre) / (t_post - t_pre) if t_post != t_pre else 0.0
    df[load_col] = df[load_col] - (F_pre + slope * (df[time_col] - t_pre))
    df.attrs["mono_drift_slope"] = slope
    df.attrs["mono_drift_baselines"] = (F_pre, F_post)
    return df


def preprocess_mono(path, threshold=6.0, min_consecutive=3):
    """Drift-correct complete cycles; only contact-zero incomplete mono curves."""
    df = load_raw_txt(path)
    info = mono_curve_metadata(df)
    try:
        if not (df["segm"] == 1).any():
            raise ValueError("No mono loading segment (segm 1)")
        if info["mono_complete"]:
            df = correct_mono_drift(df, threshold=threshold, min_consecutive=min_consecutive)
            info["drift_correction_applied"] = True
        df = zero_from_contact(df, threshold=threshold, min_consecutive=min_consecutive)
    except (ValueError, KeyError) as error:
        raise MonoPreprocessingError(str(error), info) from error
    df.attrs.update(info)
    if not df.empty:
        df.attrs["max_displ_zeroed"] = float(df["displ_zeroed"].max())
    return df


def preprocess_sr(path, target_segs, threshold=6.0, min_consecutive=3):
    """Load a stress-relaxation file, keep the target segments, zero, record ramp/hold timing."""
    df = load_raw_txt(path)
    df = zero_from_contact(df[df["segm"].isin(target_segs)].copy(),
                           threshold=threshold, min_consecutive=min_consecutive)
    if df.empty:
        return df
    d, t = df["displ_zeroed"].to_numpy(), df["time_zeroed"].to_numpy()
    max_d = float(d.max())
    t_ramp = float(t[np.argmax(d >= 0.95 * max_d)])      # time when ramp reaches 95% of max
    df.attrs.update(max_displ_zeroed=max_d, t_ramp_zeroed=t_ramp,
                    hold_duration_zeroed=float(t[-1] - t_ramp))
    return df


def preprocess_all(index, cfg, *, on_error="raise", return_report=False):
    """Preprocess curves, with optional per-curve failure reporting.

    Defaults retain strict behavior and return ``(mono_data, sr_data)``.
    With ``on_error='skip', return_report=True``, failed/empty curves are omitted
    from those dictionaries and a third DataFrame records every attempted curve.
    Skipping requires a report so failures cannot silently disappear.
    """
    if on_error not in ("raise", "skip"):
        raise ValueError("on_error must be 'raise' or 'skip'")
    if on_error == "skip" and not return_report:
        raise ValueError("Skipping failures requires return_report=True")
    mono_data, sr_data, rows = {}, {}, []
    for path in index.files:
        test_type = index.test_type(path)
        record = {"sample_id": index.sample_id(path),
                  "file_name": os.path.relpath(path, index.raw_data_dir),
                  "treatment": index.treatment(path), "test_type": test_type,
                  "preprocessing_status": "ok", "preprocessing_error": ""}
        record.update({column: pd.NA if column in ("mono_complete", "drift_correction_applied")
                       else "" for column in MONO_INFO_COLS})
        try:
            if test_type == "mono":
                data = preprocess_mono(path, cfg.CONTACT_THRESHOLD, cfg.CONTACT_MIN_CONSEC)
                target = mono_data
            elif test_type == "stress_relaxation":
                data = preprocess_sr(path, cfg.TARGET_SEGS_SR,
                                     cfg.CONTACT_THRESHOLD, cfg.CONTACT_MIN_CONSEC)
                target = sr_data
            else:
                raise ValueError(f"Unsupported test_type: {test_type}")
            if data.empty:
                raise ValueError("No data remaining after preprocessing (check target segments)")
            record.update({column: data.attrs[column] for column in MONO_INFO_COLS if column in data.attrs})
            target[path] = data
        except (ValueError, OSError, KeyError) as error:
            if on_error == "raise":
                raise ValueError(f"Preprocessing failed for {record['file_name']}: {error}") from error
            record.update(preprocessing_status="failed", preprocessing_error=str(error))
            record.update(getattr(error, "metadata", {}))
        rows.append(record)
    report = pd.DataFrame(rows, columns=["sample_id", "file_name", "treatment", "test_type",
                                         "preprocessing_status", "preprocessing_error"] + MONO_INFO_COLS)
    index.set_preprocessing_report(report)
    failed_count = int((report["preprocessing_status"] == "failed").sum())
    if failed_count:
        warnings.warn(f"{failed_count} curve(s) failed preprocessing and were skipped. "
                      "Review the preprocessing report before interpreting results.", RuntimeWarning, stacklevel=2)
    if return_report:
        return mono_data, sr_data, report
    return mono_data, sr_data
