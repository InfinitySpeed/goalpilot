import unittest
from goalpilot.probe_format import normalize


class ProbeFormatTests(unittest.TestCase):
    def test_one_stray_quote_after_number_is_repaired_without_changing_values_or_assertions(self):
        bad="def a(**kw): return kw['n']\nassert a(n=3') == 3\nassert a(n=4)==4\n"
        fixed,changes=normalize(bad)
        self.assertEqual(fixed,bad.replace("3'","3"))
        self.assertEqual(len(changes),1)
        exec(fixed,{})

    def test_valid_programs_and_quoted_numbers_are_byte_identical(self):
        for code in ('assert str(3)=="3"\n',"assert '3)'=='3)'\n",'assert "line\\nnext".splitlines()==["line","next"]\n'):
            self.assertEqual(normalize(code),(code,[]))

    def test_unknown_or_partially_repairable_syntax_is_left_invalid(self):
        for code in ('assert (\n',"assert f(n=3') == 3\nassert (\n","assert 3'abc' == 3\n"):
            self.assertEqual(normalize(code),(code,[]))
