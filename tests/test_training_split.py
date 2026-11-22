import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TrainingSplitTests(unittest.TestCase):
    def test_classifier_fit_excludes_test_and_unknown_split(self):
        from backend.chatbot import trich_xuat_thuc_the as module
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dataset.csv'
            with path.open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['Tập','Câu hỏi','Nhóm'],delimiter=';')
                writer.writeheader()
                writer.writerows([{'Tập':'Train','Câu hỏi':'Câu huấn luyện','Nhóm':'a'},
                                  {'Tập':'Test','Câu hỏi':'TEST MUST NOT FIT','Nhóm':'b'},
                                  {'Tập':'','Câu hỏi':'UNKNOWN MUST NOT FIT','Nhóm':'b'}])
            pipeline=MagicMock();pipeline.classes_=['a']
            with patch.object(module,'DATASET_CSV',path),patch.object(module,'Pipeline',return_value=pipeline):
                module.PhanLoaiIntentML()
            x,y=pipeline.fit.call_args.args
            self.assertEqual(x,['Câu huấn luyện'])
            self.assertEqual(y,['a'])
