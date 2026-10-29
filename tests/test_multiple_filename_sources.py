import tempfile
import unittest
import ast
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from cartilage_indentation.dataset import SampleIndex


class MultipleFilenameSourceTests(unittest.TestCase):
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
                tree = ast.parse(code)
                # Execute definitions without the final automatic export call.
                tree.body = tree.body[:-2]
                ns = dict(INPUT_MODE='filenames', full_index=index, index=index,
                          cfg=SimpleNamespace(OUTPUT_ROOT=str(root / 'output')), excluded_raw_paths=set())
                with patch('pandas.read_excel', side_effect=AssertionError('No Excel input')), patch(
                        'matplotlib.figure.Figure.savefig'), contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(tree, '<notebook-exporter>', 'exec'), ns)
                    manifest = ns['export_optimization_data']()
                self.assertEqual(len(manifest), 2)
                self.assertEqual(manifest.csv_file.nunique(), 2)
                self.assertEqual(set(manifest.source_label), {'first', 'second'})
                self.assertTrue(all((ns['EXPORT_ROOT'] / file).is_file() for file in manifest.csv_file))
                self.assertTrue(manifest.csv_file.str.contains('__Measurement_1_Sample_A').all())


if __name__ == '__main__':
    unittest.main()
