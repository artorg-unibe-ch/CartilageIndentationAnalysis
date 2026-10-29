"""Hertz elastic fitting of the monotonic (mono) loading curve."""
import numpy as np
from scipy.optimize import curve_fit


def hertz(d, E_star, cp, R_um):
    """Spherical-indenter Hertz model: ``F = (4/3)·E*·sqrt(R)·(d - cp)^1.5`` (0 for d <= cp)."""
    x = np.asarray(d, float) - cp
    x_pos = np.clip(x, 0.0, None)                     # avoid a negative base in the power
    return np.where(x > 0, (4.0 / 3.0) * E_star * np.sqrt(R_um) * x_pos ** 1.5, 0.0)


def get_loading(df):
    """Loading ramp = ``segm == 1`` (hold / unload / retract excluded). Uses the zeroed data."""
    L = df[df["segm"] == 1]
    return L["displ_zeroed"].values, L["load_zeroed"].values


def find_cp_moving(d, f, win=None):
    """Moving-regression contact point.

    After linearizing Hertz, ``F^(2/3)`` vs ``d`` is a straight line. Slide a fixed-width
    window along that curve, keep the most-linear window (highest R²), and extrapolate its
    line to ``F = 0``; the x-intercept is the contact point ``cp``.
    """
    d = np.asarray(d, float); f = np.asarray(f, float)
    f23 = np.sign(f) * np.abs(f) ** (2.0 / 3.0)
    n = len(d); win = win or max(12, n // 5)
    best = (-np.inf, d[0])
    for i in range(0, n - win):
        x, y = d[i:i + win], f23[i:i + win]
        m, b = np.polyfit(x, y, 1)                            # slope m, intercept b
        if m <= 0:
            continue
        r2 = 1 - np.sum((y - (m * x + b)) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-12)
        if r2 > best[0]:
            best = (r2, -b / m)                               # F = 0  ->  d = -b/m
    return best[1]


DEFAULT_P50_CP_BOUNDS_UM = (-20.0, 20.0)


def _p50_window(d, f, cp_bounds):
    if d.ndim != 1 or f.ndim != 1 or d.shape != f.shape or not len(d):
        raise ValueError("p50 requires nonempty, matching one-dimensional depth/load arrays")
    if not np.isfinite(d).all() or not np.isfinite(f).all() or f.max() <= 0:
        raise ValueError("p50 requires finite data with a positive peak load")
    lower, upper = map(float, cp_bounds)
    if not np.isfinite([lower, upper]).all() or lower >= upper:
        raise ValueError("p50 contact bounds must be finite and increasing")
    mask = f >= 0.5 * f.max()
    du, fu = d[mask], f[mask]
    if len(du) < 3 or np.ptp(du) <= 0:
        raise ValueError("p50 needs at least 3 high-load points spanning different depths")
    # A positive-load fit window must lie beyond the model's contact point.
    upper = min(upper, float(np.nextafter(du.min(), -np.inf)))
    if lower >= upper:
        raise ValueError("p50 contact bounds do not allow contact before the high-load data")
    return du, fu, lower, upper


def p50_cp_diagnostics(d, f, cp, cp_bounds=DEFAULT_P50_CP_BOUNDS_UM):
    """Record effective limits and flag a contact point close to either limit."""
    _, _, lower, upper = _p50_window(np.asarray(d, float), np.asarray(f, float), cp_bounds)
    tolerance = max(1e-6, 1e-4 * (upper - lower))
    return {"cp_lower_bound_um": lower, "cp_upper_bound_um": upper,
            "cp_at_bound": bool(cp - lower <= tolerance or upper - cp <= tolerance)}


def fit_one_curve(d, f, strat, R_um, nu, *, p50_cp_bounds=DEFAULT_P50_CP_BOUNDS_UM):
    """Hertz-fit one loading curve. ``strat`` sets how the contact point is determined:

    * ``'moving'`` — find ``cp`` by moving regression, then fix ``cp`` and fit ``E*`` only.
    * ``'p50'``    — load >= 50 % of peak; cp fitted within configurable limits
      relative to the preprocessed contact zero (default -20 to +20 µm).
      These are working limits, not a measured contact uncertainty.

    Returns ``(E_s, cp, r2, E_star, d_lo, d_hi)``, where ``E_s = E*·(1 - nu^2)`` is the
    sample modulus and ``(d_lo, d_hi)`` is the fitted depth range (for plotting).
    """
    d = np.asarray(d, float); f = np.asarray(f, float)
    if strat == "p50":
        du, fu, lower, upper = _p50_window(d, f, p50_cp_bounds)
        margin = (upper - lower) * 1e-6
        cp0 = float(np.clip(0.0, lower + margin, upper - margin))
        basis = hertz(du, 1.0, cp0, R_um)
        E0 = max(float(np.dot(basis, fu) / np.dot(basis, basis)), np.finfo(float).eps)
        (E_star, cp), _ = curve_fit(
            lambda dd, E, c: hertz(dd, E, c, R_um), du, fu,
            p0=[E0, cp0], bounds=([0, lower], [np.inf, upper]),
            x_scale="jac", maxfev=20000)
    elif strat == "moving":
        cp = find_cp_moving(d, f)
        m = d >= cp
        if m.sum() < 5:                                       # fallback if too few points
            m = d >= np.median(d)
        du, fu = d[m], f[m]
        (E_star,), _ = curve_fit(
            lambda dd, E: hertz(dd, E, cp, R_um), du, fu,
            p0=[1.0], bounds=(0, np.inf), maxfev=20000)
    else:
        raise ValueError(f"unknown strat: {strat}")
    E_s = E_star * (1 - nu ** 2)
    fp = hertz(du, E_star, cp, R_um)
    r2 = 1 - np.sum((fu - fp) ** 2) / (np.sum((fu - fu.mean()) ** 2) + 1e-12)   # R² = 1 - SS_res/SS_tot
    return E_s, cp, r2, E_star, float(du.min()), float(du.max())
