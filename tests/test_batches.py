import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from cartilage_indentation.dataset import SampleIndex, batch_comparisons
from cartilage_indentation.results import save_results
from scripts.combine_batches import combine_batches


class BatchTests(unittest.TestCase):
    def test_manifest_paths_ids_and_result_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batches = []
            for batch in ('old', 'new'):
                folder = root / batch
                folder.mkdir()
                (folder / 'same.TXT').touch()
                sheet = folder / 'samples.xlsx'
                row = dict(file_name='same.TXT', sample_id=1, treatment='Native',
                           test_type='mono', Group='Native Mono')
                batches.append((batch, sheet, folder))
            with patch('pandas.read_excel', return_value=pd.DataFrame([row])):
                rows = combine_batches(root, batches)
            self.assertEqual([r['sample_id'] for r in rows], [1, 2])
            self.assertEqual([r['original_sample_id'] for r in rows], [1, 1])
            self.assertEqual([r['file_name'] for r in rows], ['old/same.TXT', 'new/same.TXT'])
            frame = pd.DataFrame(rows)
            with patch('pandas.read_excel', return_value=frame):
                index = SampleIndex('unused', root)
            self.assertEqual([index.batch(p) for p in index.files], ['old', 'new'])
            self.assertNotEqual(*[index.line_style(p) for p in index.files])
            comparison, = batch_comparisons(index)
            self.assertEqual(comparison['files'], {'old': [index.files[0]], 'new': [index.files[1]]})
            fit = pd.DataFrame([dict(sample_id=1, Es=10, cp=0, r2=1),
                                dict(sample_id=2, Es=20, cp=0, r2=1)])
            with patch('pandas.read_excel', return_value=frame), patch.object(pd.DataFrame, 'to_excel'):
                result = save_results('unused', {'moving': fit}, None)
            self.assertEqual(list(result.Es_moving), [10, 20])
            self.assertEqual(list(result.batch), ['old', 'new'])
            with patch('pandas.read_excel', return_value=frame.assign(sample_id=1)):
                with self.assertRaisesRegex(ValueError, 'sample_id must be unique'):
                    SampleIndex('unused', root)


if __name__ == '__main__':
    unittest.main()
