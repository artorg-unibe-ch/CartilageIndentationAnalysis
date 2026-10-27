import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from cartilage_indentation.dataset import SampleIndex, treatment_comparisons, batch_comparisons
from cartilage_indentation.preprocessing import preprocess_all
from cartilage_indentation.results import save_results


def fixture_index():
    frame = pd.DataFrame([
        dict(sample_id=1, file_name='old/a.TXT', treatment='Native', test_type='mono', Group='old Native', batch='old'),
        dict(sample_id=2, file_name='new/a.TXT', treatment='Native', test_type='mono', Group='new Native', batch='new'),
        dict(sample_id=3, file_name='new/b.TXT', treatment='Degraded', test_type='stress_relaxation', Group='new Degraded', batch='new'),
    ])
    with patch('pandas.read_excel', return_value=frame):
        return SampleIndex('unused.xlsx', '/raw')


class ExclusionTests(unittest.TestCase):
    def test_union_restore_validation_and_downstream_selection(self):
        original = fixture_index()
        selected = original.excluding([1], ['new/b.TXT'])
        self.assertEqual(list(selected.sample_df.sample_id), [2])
        self.assertEqual(list(selected.excluded_df.sample_id), [1, 3])
        self.assertEqual(selected.group_order, ['new Native'])
        self.assertEqual(list(original.excluding().sample_df.sample_id), [1, 2, 3])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(treatment_comparisons(selected), [])
        self.assertEqual(batch_comparisons(selected), [])
        for kwargs in ({'sample_ids': [99]}, {'file_names': ['a.TXT']}, {'sample_ids': [1, 2, 3]}):
            with self.assertRaises(ValueError):
                original.excluding(**kwargs)
        cfg = SimpleNamespace(CONTACT_THRESHOLD=6, CONTACT_MIN_CONSEC=3, TARGET_SEGS_SR=[5, 6])
        with patch('cartilage_indentation.preprocessing.preprocess_mono', return_value=pd.DataFrame()) as mono, patch(
                'cartilage_indentation.preprocessing.preprocess_sr') as sr:
            mono_data, sr_data = preprocess_all(selected, cfg)
        mono.assert_called_once_with('/raw/new/a.TXT', 6, 3)
        sr.assert_not_called()
        self.assertEqual(list(mono_data), ['/raw/new/a.TXT'])
        self.assertEqual(sr_data, {})

    def test_filtered_save_preserves_source_and_removes_previous_fits(self):
        frame = fixture_index().sample_df.assign(Es_moving=999)
        fit = pd.DataFrame([dict(sample_id=2, Es=20, cp=0, r2=1)])
        with patch('pandas.read_excel', return_value=frame), patch.object(pd.DataFrame, 'to_excel') as write:
            result = save_results('input.xlsx', {'moving': fit}, None,
                                  output_path='filtered.xlsx', included_sample_ids=[2, 3])
            self.assertEqual(list(result.sample_id), [2, 3])
            self.assertEqual(result.iloc[0].Es_moving, 20)
            self.assertTrue(pd.isna(result.iloc[1].Es_moving))
            write.assert_called_once_with('filtered.xlsx', index=False)
            with self.assertRaisesRegex(ValueError, 'separate output_path'):
                save_results('input.xlsx', {}, None, included_sample_ids=[2])

    def test_notebook_selection_rerun_and_save_guard(self):
        nb_path = Path(__file__).resolve().parents[1] / 'notebooks' / 'analysis.ipynb'
        nb = json.loads(nb_path.read_text())
        cell = next(c for c in nb['cells'] if c.get('id') == 'curve-exclusion-selection')
        selection = ''.join(cell['source'])
        save_cell = next(''.join(c['source']) for c in nb['cells']
                         if c['cell_type'] == 'code' and 'save_options = {}' in ''.join(c['source']))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = SimpleNamespace(SAMPLE_SHEET=str(root / 'source.xlsx'))
            def reload_config(_):
                cfg.OUTPUT_ROOT = str(root / 'Analysis_Output')
                for attr in ('DIR_RAW_PLOTS', 'DIR_RAW_VS_CORR', 'DIR_COMPARISON', 'DIR_MONO_FIT'):
                    setattr(cfg, attr, str(Path(cfg.OUTPUT_ROOT) / attr))
                return cfg
            reload_config(cfg)
            ns = dict(full_index=fixture_index(), cfg=cfg, Path=Path, display=lambda *_: None,
                      importlib=__import__('importlib'), treatment_comparisons=treatment_comparisons,
                      batch_comparisons=batch_comparisons)
            with patch('importlib.reload', side_effect=reload_config), contextlib.redirect_stdout(io.StringIO()):
                exec(selection.replace('EXCLUDE_SAMPLE_IDS = []', 'EXCLUDE_SAMPLE_IDS = [1]'), ns)
                self.assertEqual(len(ns['index'].files), 2)
                self.assertEqual(ns['excluded_raw_paths'], {Path('/raw/old/a.TXT')})
                filtered_output = Path(cfg.OUTPUT_ROOT)
                self.assertTrue((filtered_output / 'excluded_samples.csv').is_file())
                self.assertEqual(list(pd.read_csv(filtered_output / 'included_samples.csv').sample_id), [2, 3])
                with self.assertRaisesRegex(RuntimeError, 'Rerun both fitting steps'):
                    exec(save_cell, ns)
                ns.update(mono_fit_selection=ns['selection_signature'], sr_fit_selection=ns['selection_signature'],
                          res_moving=pd.DataFrame(), res_p50=pd.DataFrame(), prony_df=pd.DataFrame())
                with patch('pandas.read_excel', return_value=ns['full_index'].sample_df), patch.object(pd.DataFrame, 'to_excel'):
                    ns['save_results'] = save_results
                    exec(save_cell, ns)
                self.assertEqual(list(ns['final'].sample_id), [2, 3])
                exec(selection, ns)
                self.assertEqual(len(ns['index'].files), 3)
                self.assertEqual(cfg.OUTPUT_ROOT, str(root / 'Analysis_Output'))
                self.assertEqual(ns['excluded_raw_paths'], set())
                self.assertEqual(ns['RESULTS_SHEET'], Path(cfg.SAMPLE_SHEET))


if __name__ == '__main__':
    unittest.main()
