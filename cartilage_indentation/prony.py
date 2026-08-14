"""One-term Prony (viscoelastic) fitting of the stress-relaxation curve."""
import numpy as np
from scipy.optimize import curve_fit


def sr_model_1term(t, g1, tau1, F0):
    """One-term Prony series: ``F(t) = F0 * [ge + g1·exp(-t/tau1)]``, with ``ge = 1 - g1``."""
    return F0 * ((1 - g1) + g1 * np.exp(-t / tau1))


def fit_sr_1term(df, max_time=120.0):
    """Fit one relaxation curve from the load peak to ``max_time``.

    Returns a dict with the coefficients (``g1, ge, tau1_s, F0_mN, r2_prony``) and the
    curve arrays for plotting (``td``, ``fc``), or ``None`` if the curve is too short.
    """
    t_all, f_all = df["time_zeroed"].values, df["load_zeroed"].values
    ip = int(np.argmax(f_all)); t_peak = t_all[ip]
    mask = (t_all >= t_peak) & (t_all <= max_time)
    td, fd = t_all[mask], f_all[mask]
    if len(td) <= 10:
        return None
    ts = td - t_peak                                   # shift so t = 0 at the peak
    F0 = np.median(fd[:3])                              # initial (peak) force, kept fixed
    g_guess = max((F0 - np.median(fd[-5:])) / F0, 0.05)
    (g1, tau1), _ = curve_fit(
        lambda t, g1, tau1: sr_model_1term(t, g1, tau1, F0),
        ts, fd, p0=[g_guess, 10.0],
        bounds=([0.0, 0.5], [0.95, 1000.0]),           # g1 in [0, 0.95], tau1 in [0.5, 1000] s
        maxfev=10000, method="trf")
    fc = sr_model_1term(ts, g1, tau1, F0)
    r2 = 1 - np.sum((fd - fc) ** 2) / np.sum((fd - fd.mean()) ** 2)
    return dict(g1=g1, ge=1 - g1, tau1_s=tau1, F0_mN=F0, r2_prony=r2, td=td, fc=fc)
