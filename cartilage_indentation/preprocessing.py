"""Contact detection, zeroing and baseline-drift correction.

The old "zero at the first row" is unreliable because the first sample is not the true
contact point. Instead the contact point is detected as the first row where the load
stays above a threshold for a few consecutive rows.
"""
import numpy as np

from .io_utils import load_raw_txt


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
    """Load, correct the baseline drift (mono tests are slow), then detect contact and zero."""
    df = correct_mono_drift(load_raw_txt(path), threshold=threshold, min_consecutive=min_consecutive)
    df = zero_from_contact(df, threshold=threshold, min_consecutive=min_consecutive)
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


def preprocess_all(index, cfg):
    """Preprocess every file. Returns ``(mono_data, sr_data)``: path -> processed DataFrame."""
    mono_data = {
        f: preprocess_mono(f, cfg.CONTACT_THRESHOLD, cfg.CONTACT_MIN_CONSEC)
        for g in index.subgroup_mono for f in index.subgrouped_files[g]
    }
    sr_data = {
        f: preprocess_sr(f, cfg.TARGET_SEGS_SR, cfg.CONTACT_THRESHOLD, cfg.CONTACT_MIN_CONSEC)
        for g in index.subgroup_sr for f in index.subgrouped_files[g]
    }
    return mono_data, sr_data
