import tempfile
import unittest
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from cartilage_indentation.dataset import SampleIndex, filename_output_tag


class MultipleFilenameSourceTests(unittest.TestCase):
    def test_output_folders_separate_single_and_combined_runs_under_custom_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            first = dict(path=root / 'one', label='M3', batch='20261029', recursive=False)
            second = dict(path=root / 'two', label='M1', batch='20261022', recursive=True)
            single = filename_output_tag([first])
            combined = filename_output_tag([first, second])
            self.assertTrue(single.startswith('single_M3_20261029_'))
            self.assertTrue(combined.startswith('combined_M3_M1_'))
            self.assertNotEqual(single, combined)
            self.assertEqual(combined, filename_output_tag([dict(first), dict(second)]))
            self.assertNotEqual(combined, filename_output_tag([second, first]))
            self.assertNotEqual(single, filename_output_tag([dict(first, recursive=True)]))
            notebook = json.loads((Path(__file__).resolve().parents[1] / 'notebooks/analysis.ipynb').read_text())
            setup = ''.join(next(c['source'] for c in notebook['cells'] if c.get('id') == '37b5de61'))
            calculation = setup.split('# A custom root is a BASE directory;', 1)[1].split('os.environ["CIA_DATA_ROOT"]', 1)[0]
            calculation = calculation.split('\n', 1)[1]
            for base, expected_base in [(root / 'custom', root / 'custom'),
                                        (Path('relative'), root / 'relative'),
                                        (None, root / 'Analysis_Output')]:
                for tag in (single, combined):
                    ns = dict(Path=Path, REPO_ROOT=root, ANALYSIS_OUTPUT_ROOT=base, dataset_tag=tag)
                    exec(calculation, ns)
                    self.assertEqual(ns['output_root'], expected_base / tag)

    def test_same_basename_has_unique_ids_source_groups_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            sources = []
            name = 'Measurement_3_Sample_A_native_mono_1.TXT'
            for label, batch in [('first', '20261022'), ('second', '20261026')]:
                folder = root / label
                folder.mkdir()
                (folder / name).write_text(label)
                sources.append(dict(path=folder, label=label, batch=batch, recursive=False))
            with patch('pandas.read_excel', side_effect=AssertionError('No Excel input')):
                index = SampleIndex.from_filename_sources(sources)
            self.assertEqual(index.raw_data_dir, root)
            self.assertEqual(list(index.sample_df.sample_id), [1, 2])
            self.assertEqual(list(index.sample_df.file_name), [f'first/{name}', f'second/{name}'])
            self.assertEqual(index.sample_df.Group.nunique(), 2)
            self.assertEqual(list(index.sample_df.source_label), ['first', 'second'])
            self.assertEqual(list(index.sample_df.source_file_name), [name, name])
            self.assertTrue(all(Path(path).is_file() for path in index.sample_df.source_path))
            self.assertEqual([index.batch(p) for p in index.files], ['20261022', '20261026'])
            self.assertEqual([index.sample_label(p) for p in index.files], ['#1 (M3SA)', '#2 (M3SA)'])
            filtered = index.excluding(file_names=[f'first/{name}'])
            self.assertEqual(list(filtered.sample_df.sample_id), [2])
            self.assertEqual(filtered.files, [str(root / 'second' / name)])

    def test_single_folder_preserves_relative_paths_and_group_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            name = 'Measurement_1_Sample_A_crosslinked_mono_2.TXT'
            (root / name).touch()
            index = SampleIndex.from_filename_sources([dict(path=root, batch='20261022')])
            self.assertEqual(index.sample_df.iloc[0].file_name, name)
            self.assertEqual(index.group_order, ['Measurement_1_Sample_A Crosslinked mono'])

    def test_overlap_duplicate_labels_and_invalid_names_stop_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            child = root / 'child'
            child.mkdir()
            (child / 'Measurement_1_Sample_A_native_mono_1.TXT').touch()
            with self.assertRaisesRegex(ValueError, 'more than once'):
                SampleIndex.from_filename_sources([
                    dict(path=root, label='parent', recursive=True), dict(path=child, label='child')])
            with self.assertRaisesRegex(ValueError, 'Duplicate source label'):
                SampleIndex.from_filename_sources([
                    dict(path=child, label='same'), dict(path=child, label='same')])
            (child / 'legacy# 1.TXT').touch()
            with self.assertRaisesRegex(ValueError, 'legacy# 1.TXT'):
                SampleIndex.from_filename_sources([dict(path=child)])
            with self.assertRaisesRegex(ValueError, 'at least one'):
                SampleIndex.from_filename_sources([])

    def test_both_optimization_exporters_keep_same_named_sources_separate(self):
        notebook = json.loads((Path(__file__).resolve().parents[1] / 'notebooks/analysis.ipynb').read_text())
        exporters = [''.join(c['source']) for c in notebook['cells']
                     if c['cell_type'] == 'code' and 'def export_optimization_data' in ''.join(c['source'])]
        self.assertEqual(len(exporters), 2)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            sources = []
            name = 'Measurement_1_Sample_A_native_stress_relaxation_1.TXT'
            for label in ('first', 'second'):
                folder = root / label
                folder.mkdir()
                time = np.arange(60, dtype=float)
                depth = np.r_[np.linspace(0, 20, 20), np.full(40, 20.)]
                load = np.r_[np.linspace(0, 100, 20), np.linspace(100, 60, 40)]
                segment = np.r_[np.full(20, 5), np.full(40, 6)]
                lines = ['Measured values', 'time\tdispl\tload\tref_load\tsegm']
                lines += ['\t'.join(map(str, values)) for values in zip(time, depth, load, np.zeros(60), segment)]
                (folder / name).write_text('\n'.join(lines))
                sources.append(dict(path=folder, label=label))
            index = SampleIndex.from_filename_sources(sources)
            for code in exporters:
                angle = '90' if 'RUN_OPTIMIZATION_EXPORT_90DEG' in code else '45'
                enabled = code.replace(f'RUN_OPTIMIZATION_EXPORT_{angle}DEG = False',
                                       f'RUN_OPTIMIZATION_EXPORT_{angle}DEG = True', 1)
                ns = dict(INPUT_MODE='filenames', full_index=index, index=index,
                          cfg=SimpleNamespace(OUTPUT_ROOT=str(root / 'output')), excluded_raw_paths=set(),
                          display=lambda *_: None)
                with patch('pandas.read_excel', side_effect=AssertionError('No Excel input')), patch(
                        'matplotlib.figure.Figure.savefig'), contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(enabled, '<notebook-exporter>', 'exec'), ns)
                    manifest = ns[f'optimization_manifest_{angle}deg']
                    other = next(other for other in exporters if other != code)
                    exec(other, ns)  # the other module stays disabled
                    self.assertIs(ns[f'optimization_manifest_{angle}deg'], manifest)
                self.assertEqual(len(manifest), 2)
                self.assertEqual(manifest.csv_file.nunique(), 2)
                self.assertEqual(set(manifest.source_label), {'first', 'second'})
                self.assertTrue(all((ns['EXPORT_ROOT'] / file).is_file() for file in manifest.csv_file))
                self.assertTrue(manifest.csv_file.str.contains('__Measurement_1_Sample_A').all())

    def test_export_switches_default_off_and_do_not_touch_files_or_require_inputs(self):
        notebook = json.loads((Path(__file__).resolve().parents[1] / 'notebooks/analysis.ipynb').read_text())
        exporters = [''.join(c['source']) for c in notebook['cells']
                     if c['cell_type'] == 'code' and 'def export_optimization_data' in ''.join(c['source'])]
        ns = {'INPUT_MODE': 'filenames'}  # no loaded index or dataset is required when disabled
        with patch('pathlib.Path.mkdir', side_effect=AssertionError('Must not create folders')), patch(
                'pandas.read_excel', side_effect=AssertionError('Must not read Excel')), patch(
                'pandas.DataFrame.to_csv', side_effect=AssertionError('Must not write CSVs')), patch(
                'matplotlib.figure.Figure.savefig', side_effect=AssertionError('Must not create images')), contextlib.redirect_stdout(io.StringIO()):
            for code in exporters:
                exec(code, ns)
        self.assertFalse(ns['RUN_OPTIMIZATION_EXPORT_90DEG'])
        self.assertFalse(ns['RUN_OPTIMIZATION_EXPORT_45DEG'])
        self.assertIsNone(ns['optimization_manifest_90deg'])
        self.assertIsNone(ns['optimization_manifest_45deg'])


if __name__ == '__main__':
    unittest.main()
