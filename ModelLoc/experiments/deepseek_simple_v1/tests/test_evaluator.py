import unittest
from src.metrics import scores,normalize_functions,mrr
from src.code_index import file_record
from src.gold_mapping import map_gold

class EvaluatorTests(unittest.TestCase):
    def test_slots_multitarget_empty(self):
        p=['a','a',None,'wrong','b','c'];g=['b','c']
        self.assertEqual(scores(p,g,5)['recall'],.5)
        self.assertEqual(scores(p,g,5)['precision'],.2)
        self.assertEqual(mrr(p,g),.2)
        self.assertEqual(scores([],g,5)['hit'],0)
        self.assertIsNone(scores([],[],5)['hit'])
    def test_exact_invalid_path_ambiguous_name(self):
        idx={'a.py':file_record('a.py','class A:\n def f(self): pass\nclass B:\n def f(self): pass\n')}
        pred,n=normalize_functions([{'path':'../a.py','qualified_name':'A.f'},
            {'path':'a.py','qualified_name':'f'},{'path':'./a.py','qualified_name':'B.f'}],idx)
        self.assertEqual(pred,[None,None,'a.py::B.f']);self.assertEqual(n,2)
    def test_new_function_not_nearest(self):
        patch='diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,5 @@\n def old():\n-    return 1\n+    return 2\n+\n+def new():\n+    return 3\n'
        g=map_gold(patch,{'a.py':'def old():\n    return 1\n'})
        self.assertEqual(g['gold_functions'],['a.py::old'])
        self.assertEqual(g['new_functions'],['a.py::new'])
        self.assertEqual(g['mapping_status'],'partially_mappable')

if __name__=='__main__':unittest.main()
