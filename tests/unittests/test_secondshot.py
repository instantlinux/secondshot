import binascii
import unittest2
import sys
sys.path.append('../../secondshot')

import secondshot


class TestSecondshot(unittest2.TestCase):

    def test_hashtype(self):
        ret = secondshot.Secondshot._hashtype(binascii.unhexlify(
            'd41d8cd98f00b204e9800998ecf8427e'))
        self.assertEqual(ret, 'md5')
        ret = secondshot.Secondshot._hashtype(binascii.unhexlify(
            'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852'
            'b855'))
        self.assertEqual(ret, 'sha256')
        ret = secondshot.Secondshot._hashtype(binascii.unhexlify(
            'cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36c'
            'e9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327a'
            'f927da3e'))
        self.assertEqual(ret, 'sha512')
