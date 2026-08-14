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


def fit_one_curve(d, f, strat, R_um, nu):
    """Hertz-fit one loading curve. ``strat`` sets how the contact point is determined:

    * ``'moving'`` — find ``cp`` by moving regression, then fix ``cp`` and fit ``E*`` only.
    * ``'p50'``    — use only load >= 50 % of peak, ``cp`` free.

    Returns ``(E_s, cp, r2, E_star, d_lo, d_hi)``, where ``E_s = E*·(1 - nu^2)`` is the
    sample modulus and ``(d_lo, d_hi)`` is the fitted depth range (for plotting).
    """
    d = np.asarray(d, float); f = np.asarray(f, float)
    if strat == "p50":
        m = f >= 0.5 * np.nanmax(f)                           # keep high-load part only
        du, fu = d[m], f[m]
        (E_star, cp), _ = curve_fit(
            lambda dd, E, c: hertz(dd, E, c, R_um), du, fu,
            p0=[1.0, du[0]], bounds=([0, du.min() - 20], [np.inf, du.max()]), maxfev=20000)
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
