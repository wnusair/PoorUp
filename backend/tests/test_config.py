import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import _expand_origin_list  # noqa: E402


class ConfigOriginExpansionTests(unittest.TestCase):
    def test_host_only_origin_expands_for_common_frontend_ports(self):
        origins = _expand_origin_list(['http://10.25.103.93'])

        self.assertEqual(
            origins,
            [
                'http://10.25.103.93',
                'http://10.25.103.93:3000',
                'http://10.25.103.93:4173',
                'http://10.25.103.93:5173',
            ],
        )

    def test_origin_with_explicit_port_is_left_unchanged(self):
        self.assertEqual(
            _expand_origin_list(['http://10.25.103.93:5173']),
            ['http://10.25.103.93:5173'],
        )


if __name__ == '__main__':
    unittest.main()