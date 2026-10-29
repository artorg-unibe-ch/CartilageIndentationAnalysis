import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from cartilage_indentation.dataset import SampleIndex
from cartilage_indentation.hertz import fit_one_curve, hertz, p50_cp_diagnostics
from cartilage_indentation.plotting import fit_and_plot_mono
from cartilage_indentation.results import save_results


class P50ContactBoundsTests(unittest.TestCase):
    def test_recovers_contact_far_before_high_load_window(self):
        d = np.linspace(0, 120, 601)
        for cp in (-5., 0., 12.):
            with self.subTest(cp=cp):
                f = hertz(d, .02, cp, 500)
                result = fit_one_curve(d, f, 'p50', 500, .25)
                self.assertGreater(result[4] - 20, cp)  # old bound excluded the true solution
                self.assertAlmostEqual(result[1], cp, places=4)
                self.assertAlmostEqual(result[0], .02 * (1 - .25**2), places=6)
                self.assertGreater(result[2], .999999)
                self.assertFalse(p50_cp_diagnostics(d, f, result[1])['cp_at_bound'])

    def test_custom_limits_flag_boundary_and_persist_diagnostics(self):
        d = np.linspace(0, 120, 601)
        f = hertz(d, .02, 12., 500)
        frame = pd.DataFrame([dict(sample_id=1, file_name='one.TXT', treatment='Native',
                                   test_type='mono', Group='Native mono')])
        index = SampleIndex.from_dataframe(frame, '/raw')
        pair = dict(name='Native', type='mono', treatments=('Native',),
                    files={'Native': index.files}, filename='Native.png')
        labels = []
        def capture(fig, *_args, **_kwargs):
            labels.extend(fig.axes[0].get_legend_handles_labels()[1])
        with tempfile.TemporaryDirectory() as tmp, self.assertWarnsRegex(RuntimeWarning, 'contact bound'), patch(
                'matplotlib.figure.Figure.savefig', new=capture):
            result = fit_and_plot_mono(index, [pair], {'/raw/one.TXT': (d, f)}, 'p50', 'p50',
                                      tmp, 500, .25, p50_cp_bounds=(-2, 2))
        self.assertAlmostEqual(result.iloc[0].cp, 2., places=4)
        self.assertTrue(result.iloc[0].cp_at_bound)
        self.assertIn('[cp bound]', labels[0])
        with patch.object(pd.DataFrame, 'to_excel'):
            first = save_results(None, {'p50': result}, None, metadata=frame, output_path='unused.xlsx')
            second = save_results(None, {'p50': result}, None, metadata=first, output_path='unused.xlsx')
        self.assertTrue(second.iloc[0].cp_at_bound_p50)
        self.assertEqual(second.iloc[0].cp_lower_bound_um_p50, -2.)
        self.assertEqual(second.iloc[0].cp_upper_bound_um_p50, 2.)
        self.assertEqual(len(second), 1)
        self.assertEqual(list(first.columns), list(second.columns))

    def test_bad_data_and_bounds_fail_clearly(self):
        for d, f, bounds in [
            ([], [], (-20, 20)), ([0, 1, 2], [0, 0, 0], (-20, 20)),
            ([0, 1, 2], [1, np.nan, 3], (-20, 20)),
            ([0, 1, 2], [1, 2, 3], (5, 5)),
            ([0, 1, 2], [1, 2, 3], (10, 20)),
        ]:
            with self.subTest(d=d, bounds=bounds), self.assertRaises(ValueError):
                fit_one_curve(d, f, 'p50', 500, .25, p50_cp_bounds=bounds)


if __name__ == '__main__':
    unittest.main()
