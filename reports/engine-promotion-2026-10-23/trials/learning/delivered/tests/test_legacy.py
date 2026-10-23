import unittest
from app import banner
class Legacy(unittest.TestCase):
 def test_banner(self):self.assertEqual(banner(),'Local Ops — café')
