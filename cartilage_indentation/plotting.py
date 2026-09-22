"""Figure generation (raw vs corrected, Native-vs-UV comparison, Hertz & Prony fits).

The fitting functions also return the per-sample fit parameters as DataFrames.
A non-interactive matplotlib backend is used so figures are saved without a display.
"""
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt   # backend auto-selected (Agg if headless; inline in notebooks)

from .io_utils import load_raw_txt
from .hertz import hertz, fit_one_curve
from .prony import fit_sr_1term


def _safe(name):
    return "".join(c for c in name if c.isalnum() or c == " ").strip()


def plot_raw_vs_corrected(index, mono_data, sr_data, out_dir):
    """One figure per group: raw data (left) vs. corrected/zeroed data (right)."""
    os.makedirs(out_dir, exist_ok=True)
    palette = plt.cm.tab10.colors
    for group_name in index.group_order:
        test_type = index.group_ttype[group_name]
        group_files = index.subgrouped_files[group_name]
        if not group_files:
            continue
        fig, (ax_raw, ax_corr) = plt.subplots(1, 2, figsize=(16, 5))
        for i, path in enumerate(group_files):
            s_id = index.sample_id(path)
            color = palette[i % len(palette)]
            raw = load_raw_txt(path)
            corr = mono_data.get(path) if test_type == "mono" else sr_data.get(path)
            if test_type == "mono":
                ax_raw.plot(raw["displ"], raw["load"], color=color, label=f"Sample #{s_id}")
                if corr is not None and not corr.empty:
                    ax_corr.plot(corr["displ_zeroed"], corr["load_zeroed"], color=color, label=f"Sample #{s_id}")
                ax_raw.set_xlabel("displ [µm]"); ax_corr.set_xlabel("displ_zeroed [µm]")
            else:
                ax_raw.plot(raw["time"], raw["load"], color=color, label=f"Sample #{s_id}")
                if corr is not None and not corr.empty:
                    ax_corr.plot(corr["time_zeroed"], corr["load_zeroed"], color=color, label=f"Sample #{s_id}")
                ax_raw.set_xlabel("time [s]"); ax_corr.set_xlabel("time_zeroed [s]")
        ax_raw.set_title("Raw"); ax_corr.set_title("Corrected")
        ax_raw.set_ylabel("load [mN]"); ax_corr.set_ylabel("load_zeroed [mN]")
        for ax in (ax_raw, ax_corr):
            ax.grid(True, linestyle="--", alpha=0.5)
        ax_corr.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)
        fig.suptitle(group_name, fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"{_safe(group_name)}_{test_type}_raw_vs_corrected.png"),
                    dpi=300, bbox_inches="tight")
        plt.close(fig)


def plot_comparison_native_uv(index, pairs, mono_data, sr_data, out_dir):
    """One figure per Native-vs-UV pair, overlaying the corrected curves."""
    os.makedirs(out_dir, exist_ok=True)
    for paar in pairs:
        native_files = index.subgrouped_files.get(paar["native_key"], [])
        uv_files = index.subgrouped_files.get(paar["uv_key"], [])
        nN, nU = max(1, len(native_files)), max(1, len(uv_files))
        blues = [plt.cm.Blues(x) for x in np.linspace(0.4, 0.95, nN)] if nN > 1 else [plt.cm.Blues(0.7)]
        reds  = [plt.cm.Reds(x)  for x in np.linspace(0.4, 0.95, nU)] if nU > 1 else [plt.cm.Reds(0.7)]
        fig = plt.figure(figsize=(11, 6))
        has_data = False
        for files_, shades, tag in [(native_files, blues, "Native"), (uv_files, reds, "UV")]:
            for i, path in enumerate(files_):
                df = mono_data.get(path) if paar["type"] == "mono" else sr_data.get(path)
                if df is None or df.empty:
                    continue
                s_id = index.sample_id(path)
                if paar["type"] == "mono":
                    plt.plot(df["displ_zeroed"], df["load_zeroed"], color=shades[i], label=f"{tag} #{s_id}")
                else:
                    plt.plot(df["time_zeroed"], df["load_zeroed"], color=shades[i], label=f"{tag} #{s_id}")
                has_data = True
        if not has_data:
            plt.close(fig)
            print(f"skip  no matching data for {paar['name']}")
            continue
        plt.ylabel("load_zeroed [mN]")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.title(f"{paar['name']} Native vs. UV", fontsize=12, fontweight="bold")
        if paar["type"] == "mono":
            plt.xlabel("Displacement [µm]")
        else:
            plt.xlabel("time [s]"); plt.xlim(0, 130)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, paar["filename"]), dpi=300, bbox_inches="tight")
        plt.close(fig)


def fit_and_plot_mono(index, pairs, mono_loading, strat, method_name, out_dir, R_um, nu):
    """Hertz-fit EVERY mono loading curve (independent of Native/UV pairing), then draw the
    Native-vs-UV comparison figures for paired groups.

    Returns a DataFrame with one row per mono sample: ``group, treatment, sample_id, Es, cp, r2``.
    """
    os.makedirs(out_dir, exist_ok=True)

    # 1) Fit every mono sample, so none is skipped just because it has no UV partner.
    fits = {}   # path -> (E_s, cp, r2, E_star, d_lo, d_hi)
    rows = []
    for g in index.subgroup_mono:
        for path in index.subgrouped_files[g]:
            if path not in mono_loading:
                continue
            d, f = mono_loading[path]
            try:
                fits[path] = fit_one_curve(d, f, strat, R_um, nu)
            except Exception as e:
                print(f"mono fit failed #{index.sample_id(path)} ({g}): {e}")
                continue
            E_s, cp, r2 = fits[path][0], fits[path][1], fits[path][2]
            rows.append({"group": g, "treatment": index.treatment(path),
                         "sample_id": index.sample_id(path), "Es": E_s, "cp": cp, "r2": r2})

    # 2) Comparison figures per Native/UV pair (reuse the fits above).
    for paar in pairs:
        if paar["type"] != "mono":
            continue
        nf = index.subgrouped_files.get(paar["native_key"], [])
        uf = index.subgrouped_files.get(paar["uv_key"], [])
        fig, ax = plt.subplots(figsize=(12, 7))
        blues = [plt.cm.Blues(x) for x in np.linspace(0.5, 0.95, max(1, len(nf)))]
        reds  = [plt.cm.Reds(x)  for x in np.linspace(0.5, 0.95, max(1, len(uf)))]
        for files_, shades, tag in [(nf, blues, "Native"), (uf, reds, "UV")]:
            for i, path in enumerate(files_):
                if path not in fits:
                    continue
                s_id = index.sample_id(path)
                d, f = mono_loading[path]
                E_s, cp, r2, E_star, d_lo, d_hi = fits[path]
                # x-axis = the real indentation depth (displ_zeroed); the fit rises at its own cp
                ax.plot(d, f, color=shades[i], lw=1.2, alpha=0.3)        # raw loading data (full)
                dd = np.linspace(d_lo, d_hi, 100)                        # draw the fit only over the fitted region
                ax.plot(dd, hertz(dd, E_star, cp, R_um), color=shades[i], lw=2.5,
                        label=f"{tag} #{s_id} (Es={E_s:.3f}, R²={r2:.2f})")
        ax.set_title(f"{paar['name']} - {method_name}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Indentation Depth [µm]"); ax.set_ylabel("Load [mN]")
        ax.grid(True, ls="--", alpha=0.5)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        fig.tight_layout()
        fname = f"{paar['filename'].replace('.png', '')}_{_safe(method_name).replace(' ', '_')}.png"
        fig.savefig(os.path.join(out_dir, fname), dpi=200, bbox_inches="tight")
        plt.close(fig)
    return pd.DataFrame(rows)


def fit_and_plot_sr(index, pairs, sr_data, out_dir, max_time=120.0):
    """1-term Prony fit for EVERY SR curve (independent of pairing), plus Native-vs-UV figures.

    Returns a DataFrame with one row per SR sample: ``sample_id, g1, ge, tau1_s, F0_mN, r2_prony``.
    """
    os.makedirs(out_dir, exist_ok=True)

    # 1) Fit every stress-relaxation sample.
    res_by_path = {}   # path -> result dict from fit_sr_1term
    prony_rows = []
    for g in index.subgroup_sr:
        for path in index.subgrouped_files[g]:
            df = sr_data.get(path)
            if df is None or df.empty:
                continue
            try:
                res = fit_sr_1term(df, max_time)
            except Exception as e:
                print(f"SR fit error #{index.sample_id(path)} ({g}): {e}")
                res = None
            if res is None:
                continue
            res_by_path[path] = res
            prony_rows.append({"sample_id": index.sample_id(path), "g1": res["g1"], "ge": res["ge"],
                               "tau1_s": res["tau1_s"], "F0_mN": res["F0_mN"], "r2_prony": res["r2_prony"]})

    # 2) Comparison figures per Native/UV pair.
    for paar in [p for p in pairs if p["type"] == "stress_relaxation"]:
        nf = index.subgrouped_files.get(paar["native_key"], [])
        uf = index.subgrouped_files.get(paar["uv_key"], [])
        nN, nU = max(1, len(nf)), max(1, len(uf))
        blues = [plt.cm.Blues(x) for x in np.linspace(0.4, 0.95, nN)] if nN > 1 else [plt.cm.Blues(0.7)]
        reds  = [plt.cm.Reds(x)  for x in np.linspace(0.4, 0.95, nU)] if nU > 1 else [plt.cm.Reds(0.7)]
        fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
        has_data = False
        for files_, shades, tag in [(nf, blues, "Native"), (uf, reds, "UV")]:
            for i, path in enumerate(files_):
                df = sr_data.get(path)
                if df is None or df.empty:
                    continue
                s_id = index.sample_id(path); color = shades[i]
                ax.plot(df["time_zeroed"].values, df["load_zeroed"].values,
                        color=color, lw=1.5, alpha=0.15, linestyle="--")   # raw, faint
                res = res_by_path.get(path)
                if res is None:
                    continue
                ax.plot(res["td"], res["fc"], color=color, lw=2.5, alpha=0.8,
                        label=f"{tag} #{s_id} Fit (τ={res['tau1_s']:.1f}s, "
                              f"g1={res['g1']:.2f}, R²={res['r2_prony']:.2f})")
                has_data = True
        if has_data:
            ax.set_ylabel("load_zeroed [mN]"); ax.set_xlabel("Time [s]")
            ax.set_xlim(-0.5, 130); ax.grid(True, linestyle="--", alpha=0.5)
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
            ax.set_title(f"{paar['name']} — Stress Relaxation (1-term Prony)",
                         fontsize=12, fontweight="bold")
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, paar["filename"].replace(".png", "_1term.png")),
                        dpi=300, bbox_inches="tight")
        plt.close(fig)
    cols = ["sample_id", "g1", "ge", "tau1_s", "F0_mN", "r2_prony"]
    if not prony_rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(prony_rows).sort_values("sample_id").reset_index(drop=True)
