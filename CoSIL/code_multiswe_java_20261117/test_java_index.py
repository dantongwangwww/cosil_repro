import tempfile
from pathlib import Path
import unittest

from code_multiswe_java_20261117.java_index import parse_java, build_index, direct_edges


class JavaIndexTests(unittest.TestCase):
    def test_overloads_constructors_interfaces_and_nested(self):
        raw = b'''package sample;
import java.util.List;
class Outer {
 Outer() {}
 Outer(int x) {}
 void f(String x) {}
 void f(int x) {}
 void arr(String a[], int... xs) {}
 interface Inner { static boolean valid(String text) { return true; } void a(); }
}'''
        e = parse_java('src/Outer.java', raw)
        q = {x['qualified_name'] for x in e['definitions']}
        self.assertEqual(q, {'Outer.<init>()', 'Outer.<init>(int)', 'Outer.f(String)',
                             'Outer.f(int)', 'Outer.arr(String[],int[])',
                             'Outer.Inner.valid(String)', 'Outer.Inner.a()'})
        self.assertTrue(e['complete'])
        for d in e['definitions']:
            self.assertEqual(d['code'].encode(), raw[d['start_byte']:d['end_byte']])
            self.assertEqual(d['canonical_id'], 'src/Outer.java::' + d['qualified_name'])

    def test_local_and_anonymous_owners_are_distinct(self):
        raw = b'''class O {
void a(){class L{void x(){}}; Object b=new B(){ void x(){} };}
void b(){class L{void x(){}}; Object b=new B(){ void x(){} };}
}'''
        e = parse_java('O.java', raw)
        xs = [d for d in e['definitions'] if d['name'] == 'x']
        self.assertEqual(len(xs), 4)
        self.assertEqual(len({d['canonical_id'] for d in xs}), 4)
        self.assertTrue(any('<local:' in x['qualified_name'] for x in xs))
        self.assertTrue(any('<anonymous@' in x['qualified_name'] for x in xs))

    def test_conservative_edges_do_not_fanout_overloads(self):
        e = parse_java('A.java', b'''class A {
void yes(){} void f(int x){} void f(String x){}
void run(){ yes(); f(1); object.yes(); }
}''')
        g = direct_edges({'A.java': e})
        self.assertEqual([x['callee'] for x in g['edges']], ['A.java::A.yes()'])
        self.assertEqual(len(g['unresolved']), 2)
        self.assertTrue(any(x['reason'] == 'ambiguous_overload' for x in g['unresolved']))

    def test_parse_error_is_explicit(self):
        e = parse_java('Broken.java', b'class A { void broken( }')
        self.assertFalse(e['complete'])
        self.assertTrue(e['has_parse_error'])
        with self.assertRaises(ValueError):
            parse_java('../bad.java', b'class A {}')

    def test_build_index_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'A.java').write_text('class A {}')
            (root/'link.java').symlink_to(root/'A.java')
            self.assertEqual(list(build_index(root)), ['A.java'])


if __name__ == '__main__':
    unittest.main()
