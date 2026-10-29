import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from cartilage_indentation.dataset import SampleIndex
from cartilage_indentation.preprocessing import preprocess_all
from cartilage_indentation.results import save_results
from cartilage_indentation import plotting


class PreprocessingFailureTests(unittest.TestCase):
    def setUp(self):
        self.metadata = pd.DataFrame([
            dict(sample_id=1, file_name='bad.TXT', treatment='Native', test_type='mono', Group='Native mono'),
            dict(sample_id=2, file_name='good.TXT', treatment='Native', test_type='mono', Group='Native mono'),
            dict(sample_id=3, file_name='empty.TXT', treatment='Native', test_type='stress_relaxation', Group='Native SR'),
        ])
        self.index = SampleIndex.from_dataframe(self.metadata, '/raw')
        self.cfg = SimpleNamespace(CONTACT_THRESHOLD=6, CONTACT_MIN_CONSEC=3, TARGET_SEGS_SR=[5, 6])
        self.good = pd.DataFrame(dict(displ=[1., 2.], load=[7., 8.],
                                      displ_zeroed=[0., 1.], load_zeroed=[0., 1.]))

    def test_skip_reports_failures_and_continues_to_other_test_types(self):
        with patch('cartilage_indentation.preprocessing.preprocess_mono',
                   side_effect=[ValueError('No stable region'), self.good]), patch(
                'cartilage_indentation.preprocessing.preprocess_sr', return_value=pd.DataFrame()), self.assertWarnsRegex(
                    RuntimeWarning, '2 curve'):
            mono, sr, report = preprocess_all(self.index, self.cfg, on_error='skip', return_report=True)
        self.assertEqual(list(mono), ['/raw/good.TXT'])
        self.assertEqual(sr, {})
        self.assertEqual(list(report.preprocessing_status), ['failed', 'ok', 'failed'])
        self.assertIn('No stable region', report.iloc[0].preprocessing_error)
        self.assertIn('No data remaining', report.iloc[2].preprocessing_error)
        with patch('cartilage_indentation.plotting.load_raw_txt', return_value=self.good) as read, patch(
                'matplotlib.figure.Figure.savefig') as save, tempfile.TemporaryDirectory() as tmp:
            plotting.plot_raw_vs_corrected(self.index, mono, sr, tmp)
            read.assert_called_once_with('/raw/good.TXT')
            self.assertEqual(save.call_count, 1)

    def test_strict_error_names_file_and_skipping_requires_report(self):
        with patch('cartilage_indentation.preprocessing.preprocess_mono', side_effect=ValueError('No stable region')):
            with self.assertRaisesRegex(ValueError, 'bad.TXT: No stable region'):
                preprocess_all(self.index, self.cfg)
        with self.assertRaisesRegex(ValueError, 'requires return_report'):
            preprocess_all(self.index, self.cfg, on_error='skip')

    def test_report_is_saved_and_failed_sample_cannot_keep_fit_values(self):
        report = pd.DataFrame(dict(sample_id=[1, 2, 3], preprocessing_status=['failed', 'ok', 'failed'],
                                   preprocessing_error=['No stable region', '', 'Empty segments']))
        fit = pd.DataFrame([dict(sample_id=1, Es=999., cp=1., r2=1.),
                            dict(sample_id=2, Es=2., cp=0., r2=.99)])
        with patch.object(pd.DataFrame, 'to_excel') as write:
            result = save_results(None, {'moving': fit}, None, metadata=self.metadata,
                                  output_path=Path('results.xlsx'), preprocessing_report=report)
        write.assert_called_once_with(Path('results.xlsx'), index=False)
        self.assertEqual(list(result.sample_id), [1, 2, 3])
        self.assertTrue(pd.isna(result.iloc[0].Es_moving))
        self.assertEqual(result.iloc[1].Es_moving, 2.)
        self.assertEqual(result.iloc[0].preprocessing_error, 'No stable region')
        self.assertNotIn('preprocessing_status', self.metadata)
        with self.assertRaisesRegex(ValueError, 'every result sample'):
            save_results(None, {}, None, metadata=self.metadata, output_path='unused.xlsx',
                         preprocessing_report=report.iloc[:1])


if __name__ == '__main__':
    unittest.main()
