import unittest2

from secondshot import Config


class TestConfig(unittest2.TestCase):

    def test_validate_configs(self):
        cfg = Config()
        cfg.validate_configs(dict(hashtype='sha256'), ['hashtype'])
        cfg.validate_configs(dict(autoverify='yes'), ['autoverify'])
        with self.assertRaises(ValueError):
            cfg.validate_configs(dict(format='badvalue'), ['format'])
        with self.assertRaises(ValueError):
            cfg.validate_configs(dict(boguskeyword='test'), ['command'])

    def test_docopt_convert(self):
        ret = Config().docopt_convert({'--test': 'value'})
        self.assertEqual(ret, {'test': 'value'})
