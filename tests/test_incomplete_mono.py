import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from cartilage_indentation.dataset import SampleIndex
from cartilage_indentation.hertz import get_loading, hertz
from cartilage_indentation.plotting import fit_and_plot_mono, plot_raw_vs_corrected, plot_treatment_comparisons
from cartilage_indentation.preprocessing import (preprocess_mono, preprocess_all,
                                               zero_from_contact, correct_mono_drift)
from cartilage_indentation.results import save_results


def raw_curve(complete=False):
    depth = np.r_[np.linspace(-2, -0.1, 20), np.linspace(0, 20, 240)]
    load = hertz(depth, 0.02, 0, 500)
    segments = np.r_[np.zeros(20), np.ones(240)]
    if complete:
        depth = np.r_[depth, np.linspace(20, 0, 100), np.linspace(-.1, -5, 20)]
        load = np.r_[load, np.linspace(load[-1], 0, 100), np.zeros(20)]
        segments = np.r_[segments, np.full(100, 3), np.full(20, 4)]
    return pd.DataFrame(dict(time=np.arange(len(depth), dtype=float), displ=depth,
                             load=load, ref_load=np.zeros(len(depth)), segm=segments))


class IncompleteMonoTests(unittest.TestCase):
    def test_loading_only_uses_exact_contact_zeroing_without_drift(self):
        raw = raw_curve()
        with patch('cartilage_indentation.preprocessing.load_raw_txt', return_value=raw), patch(
                'cartilage_indentation.preprocessing.correct_mono_drift', side_effect=AssertionError('No drift allowed')):
            actual = preprocess_mono('loading_only.TXT')
        expected = zero_from_contact(raw)
        pd.testing.assert_frame_equal(actual, expected)
        self.assertFalse(actual.attrs['mono_complete'])
        self.assertFalse(actual.attrs['drift_correction_applied'])
        self.assertEqual(actual.attrs['preprocessing_method'], 'contact_zeroing_only')
        self.assertGreater(get_loading(actual)[1].max(), 0)

    def test_complete_cycle_retains_previous_correction(self):
        raw = raw_curve(complete=True)
        expected = zero_from_contact(correct_mono_drift(raw))
        with patch('cartilage_indentation.preprocessing.load_raw_txt', return_value=raw):
            actual = preprocess_mono('complete.TXT')
        pd.testing.assert_frame_equal(actual, expected)
        self.assertTrue(actual.attrs['mono_complete'])
        self.assertTrue(actual.attrs['drift_correction_applied'])

    def test_unloading_without_retraction_baseline_is_incomplete(self):
        raw = raw_curve(complete=True)
        for truncated in (raw[raw.segm != 4], raw.iloc[:-10]):
            with patch('cartilage_indentation.preprocessing.load_raw_txt', return_value=truncated), patch(
                    'cartilage_indentation.preprocessing.correct_mono_drift', side_effect=AssertionError('No baseline')):
                actual = preprocess_mono('truncated.TXT')
            self.assertFalse(actual.attrs['mono_complete'])
            self.assertIn('missing_post_retraction_baseline', actual.attrs['mono_incomplete_reason'])

    def test_incomplete_curves_are_fitted_labeled_and_saved(self):
        metadata = pd.DataFrame([dict(sample_id=1, file_name='loading.TXT', treatment='Native',
                                      test_type='mono', Group='Native mono')])
        index = SampleIndex.from_dataframe(metadata, '/raw')
        cfg = SimpleNamespace(CONTACT_THRESHOLD=6, CONTACT_MIN_CONSEC=3, TARGET_SEGS_SR=[5, 6])
        with patch('cartilage_indentation.preprocessing.load_raw_txt', return_value=raw_curve()):
            mono, sr, report = preprocess_all(index, cfg, return_report=True)
        self.assertEqual(report.iloc[0].preprocessing_status, 'ok')
        self.assertFalse(report.iloc[0].mono_complete)
        comparison = dict(name='Native', type='mono', treatments=('Native',),
                          files={'Native': index.files}, filename='Native.png')
        labels = []
        def capture(fig, *_args, **_kwargs):
            labels.extend(fig.axes[-1].get_legend_handles_labels()[1])
        with tempfile.TemporaryDirectory() as tmp, patch('matplotlib.figure.Figure.savefig', new=capture), patch(
                'cartilage_indentation.plotting.load_raw_txt', return_value=raw_curve()):
            plot_raw_vs_corrected(index, mono, sr, tmp)
            plot_treatment_comparisons(index, [comparison], mono, sr, tmp)
            fits = {}
            for method in ('moving', 'p50'):
                fits[method] = fit_and_plot_mono(index, [comparison],
                    {p: get_loading(d) for p, d in mono.items()}, method, method, tmp, 500, .25)
                self.assertEqual(len(fits[method]), 1)
                self.assertFalse(fits[method].iloc[0].mono_complete)
                self.assertGreater(fits[method].iloc[0].r2, .95)
        self.assertEqual(len(labels), 4)
        self.assertTrue(all('[incomplete; no drift correction]' in label for label in labels))
        with patch.object(pd.DataFrame, 'to_excel'):
            results = save_results(None, fits, None, metadata=metadata,
                                   preprocessing_report=report, output_path='unused.xlsx')
        self.assertFalse(results.iloc[0].mono_complete)
        self.assertEqual(results.iloc[0].preprocessing_status, 'ok')
        self.assertTrue(np.isfinite(results.iloc[0].Es_moving))
        self.assertTrue(np.isfinite(results.iloc[0].Es_p50))


if __name__ == '__main__':
    unittest.main()
