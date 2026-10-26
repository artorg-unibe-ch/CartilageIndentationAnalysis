import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

from cartilage_indentation.dataset import SampleIndex, TREATMENTS, treatment_comparisons
from cartilage_indentation import plotting


def make_index(omit=()):
    rows = []
    for test_type in ("mono", "stress_relaxation"):
        for treatment in TREATMENTS:
            if treatment in omit:
                continue
            n = len(rows) + 1
            rows.append(dict(file_name=f"{n}.TXT", sample_id=n, treatment=treatment,
                             test_type=test_type, Group=f"arbitrary label {n}"))
    with patch("pandas.read_excel", return_value=pd.DataFrame(rows)):
        return SampleIndex("unused.xlsx", "/raw")


class TreatmentComparisonTests(unittest.TestCase):
    def test_complete_and_missing_treatments(self):
        index = make_index()
        comparisons = treatment_comparisons(index)
        self.assertEqual(len(comparisons), 12)
        self.assertEqual(len({p["filename"] for p in comparisons}), 12)
        for test_type in ("mono", "stress_relaxation"):
            selected = [p for p in comparisons if p["type"] == test_type]
            self.assertEqual([p["treatments"] for p in selected],
                             [("Native", t) for t in TREATMENTS[1:]] + [
                                 ("Degraded", "Degraded_after_crosslinked"),
                                 ("Crosslinked", "Degraded_after_crosslinked"), TREATMENTS])
            for comparison in selected:
                for treatment, paths in comparison["files"].items():
                    self.assertTrue(paths)
                    self.assertTrue(all(index.test_type(p) == test_type and
                                        index.treatment(p) == treatment for p in paths))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            partial = treatment_comparisons(make_index(omit=("Degraded",)))
        self.assertEqual(len(partial), 6)
        self.assertIn("missing Degraded", output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            without_native = treatment_comparisons(make_index(omit=("Native",)))
        self.assertEqual(len(without_native), 4)
        self.assertTrue(all("Native" not in p["treatments"] for p in without_native))
        with contextlib.redirect_stdout(io.StringIO()):
            without_after_cl = treatment_comparisons(make_index(omit=("Degraded_after_crosslinked",)))
        self.assertEqual(len(without_after_cl), 4)
        self.assertTrue(all("Degraded_after_crosslinked" not in p["treatments"] for p in without_after_cl))

    def test_all_plot_paths_and_fit_results(self):
        index = make_index()
        comparisons = treatment_comparisons(index)
        mono, sr, loading = {}, {}, {}
        for path in index.files:
            if index.test_type(path) == "mono":
                d = np.linspace(0, 10, 200)
                f = plotting.hertz(d, 0.01, 0.0, 500.0)
                mono[path] = pd.DataFrame(dict(displ_zeroed=d, load_zeroed=f))
                loading[path] = (d, f)
            else:
                t = np.linspace(0, 120, 241)
                sr[path] = pd.DataFrame(dict(time_zeroed=t,
                                             load_zeroed=100 * (0.4 + 0.6 * np.exp(-t / 20))))
        saved = []
        def capture(fig, filename, **kwargs):
            labels = fig.axes[0].get_legend_handles_labels()[1]
            expected = TREATMENTS if "All_four" in filename else next(
                p["treatments"] for p in sorted(comparisons, key=lambda p: -len(p["filename"])) if
                p["filename"].removesuffix(".png") in filename)
            for treatment in expected:
                self.assertTrue(any(label.startswith(treatment + " #") for label in labels))
            saved.append(filename)
        with tempfile.TemporaryDirectory() as directory, patch(
                "matplotlib.figure.Figure.savefig", new=capture):
            plotting.plot_treatment_comparisons(index, comparisons, mono, sr, directory)
            for method in ("moving", "p50"):
                result = plotting.fit_and_plot_mono(index, comparisons, loading, method,
                                                   method, directory, 500.0, 0.25)
                self.assertEqual(len(result), 4)
            result = plotting.fit_and_plot_sr(index, comparisons, sr, directory)
            self.assertEqual(len(result), 4)
            self.assertIn("F0_mN", result.columns)
            self.assertTrue(np.isfinite(result["tau1_s"]).all())
        self.assertEqual(len(saved), 30)
        self.assertEqual(len(set(saved)), 30)


if __name__ == "__main__":
    unittest.main()
