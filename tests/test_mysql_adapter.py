import unittest
from backend.chatbot.co_so_du_lieu_mysql import Hang,doi_tham_so


class AdapterTests(unittest.TestCase):
    def test_row_mapping_and_index(self):
        row=Hang({'ten':'Bảo Trâm','vai_tro':'admin'})
        self.assertEqual(row[0],'Bảo Trâm')
        self.assertEqual(row['vai_tro'],'admin')
        self.assertEqual(dict(row),{'ten':'Bảo Trâm','vai_tro':'admin'})

    def test_literal_and_bind(self):
        self.assertEqual(doi_tham_so("SELECT '?' AS literal, ? AS value"),"SELECT '?' AS literal, %s AS value")
        self.assertEqual(doi_tham_so("SELECT '100% rau?' AS x, ?"),"SELECT '100%% rau?' AS x, %s")


if __name__=='__main__':
    unittest.main()
