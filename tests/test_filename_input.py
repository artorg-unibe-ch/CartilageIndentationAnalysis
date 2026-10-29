import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from cartilage_indentation.dataset import SampleIndex, metadata_from_filenames
from cartilage_indentation.results import save_results


class FilenameInputTests(unittest.TestCase):
    def test_parsing_identity_aliases_case_and_duplicate_curve_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = [
                'Measurement_3_Sample_A_native_mono_2.TXT',
                'Measurement_3_Sample_A_crosslinked_stress_relaxation_10.TXT',
                'measurement_3_sample_b_DEGRADED_stress_relaxation_38.txt',
                'Measurement_3_Sample_B_degraded_after_crosslinking_mono_38.TXT',
            ]
            for name in reversed(names):
                (root / name).touch()
            (root / 'Native_A.mit').touch()
            with patch('pandas.read_excel', side_effect=AssertionError('Excel must not be read')):
                index = SampleIndex.from_filenames(root, batch='20261029')
            d = index.sample_df
            self.assertEqual(list(d.sample_id), [1, 2, 3, 4])
            self.assertEqual(list(d.curve_number), [2, 10, 38, 38])
            self.assertEqual(set(d.sample_name), {'Measurement_3_Sample_A', 'Measurement_3_Sample_B'})
            after = d[d.status == 'degraded_after_crosslinking'].iloc[0]
            self.assertEqual(after.treatment, 'Degraded_after_crosslinked')
            self.assertEqual(after.Group, 'Measurement_3_Sample_B Degraded_after_crosslinked mono')
            self.assertEqual(set(d.batch), {'20261029'})
            self.assertEqual(index.excluding(file_names=[names[0]]).sample_df.shape[0], 3)
            pd.testing.assert_frame_equal(d, metadata_from_filenames(root, batch='20261029'))

    def test_failures_and_explicit_recursive_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'No .TXT'):
                SampleIndex.from_filenames(root)
            sub = root / 'raw'
            sub.mkdir()
            (sub / 'Measurement_1_Sample_C_native_mono_1.TXT').touch()
            self.assertEqual(len(SampleIndex.from_filenames(root, recursive=True).files), 1)
            (root / 'wrong_test_type.TXT').touch()
            with self.assertRaisesRegex(ValueError, 'wrong_test_type.TXT'):
                SampleIndex.from_filenames(root, recursive=True)
            with self.assertRaises(FileNotFoundError):
                SampleIndex.from_filenames(root / 'missing')

    def test_notebook_filename_save_without_excel_input(self):
        nb = json.loads((Path(__file__).resolve().parents[1] / 'notebooks/analysis.ipynb').read_text())
        save_cell = next(''.join(c['source']) for c in nb['cells']
                         if c['cell_type'] == 'code' and 'save_options = {}' in ''.join(c['source']))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Measurement_3_Sample_A_native_mono_1.TXT').touch()
            (root / 'Measurement_3_Sample_B_degraded_mono_1.TXT').touch()
            full = SampleIndex.from_filenames(root)
            selected = full.excluding(sample_ids=[2])
            fit = pd.DataFrame([dict(sample_id=1, Es=2.5, cp=0, r2=1)])
            ns = dict(INPUT_MODE='filenames', index=selected, selection_signature='test',
                      mono_fit_selection='test', sr_fit_selection='test',
                      RESULTS_SHEET=root / 'out.xlsx', cfg=type('Config', (), {'SAMPLE_SHEET': 'absent.xlsx'})(),
                      res_moving=fit, res_p50=pd.DataFrame(), prony_df=pd.DataFrame(),
                      save_results=save_results, display=lambda *_: None)
            before = selected.sample_df.copy()
            with patch('pandas.read_excel', side_effect=AssertionError('Excel must not be read')), patch.object(
                    pd.DataFrame, 'to_excel') as write, contextlib.redirect_stdout(io.StringIO()):
                exec(save_cell, ns)
                write.assert_called_once_with(root / 'out.xlsx', index=False)
            self.assertEqual(list(ns['final'].sample_id), [1])
            self.assertEqual(ns['final'].iloc[0].sample_name, 'Measurement_3_Sample_A')
            self.assertEqual(ns['final'].iloc[0].Es_moving, 2.5)
            pd.testing.assert_frame_equal(selected.sample_df, before)
            with self.assertRaisesRegex(ValueError, 'requires an output_path'):
                save_results(None, {}, None, metadata=before)


if __name__ == '__main__':
    unittest.main()
