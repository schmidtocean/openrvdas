#!/usr/bin/env python3

import logging
import sys
import unittest

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from logger.utils.das_record import DASRecord  # noqa: E402
from local.soi.modules.slopeintercept_transform import SlopeInterceptTransform  # noqa: E402

TEST_DATA = [
    {'input_field': 2},
    {'input_field': 5},
    {'input_field': -3}
]

EXPECTED_RESULTS = [
    {'output_field': 3},    # y = 1 * 2 + 1
    {'output_field': 6},    # y = 1 * 5 + 1
    {'output_field': -2}    # y = 1 * -3 + 1
]

class TestSlopeInterceptTransform(unittest.TestCase):
    def assertRecursiveAlmostEqual(self, val1, val2, max_diff=0.00001):
        """Check for almost equality between two values/dicts/lists/sets."""
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            self.assertLess(abs(val1-val2), max_diff)
            return

        if isinstance(val1, (str, bool, type(None))):
            self.assertEqual(val1, val2)
            return

        self.assertTrue(isinstance(val1, (set, list, dict)))
        self.assertEqual(type(val1), type(val2))
        self.assertEqual(len(val1), len(val2))

        if isinstance(val1, list):
            for i in range(len(val1)):
                self.assertRecursiveAlmostEqual(val1[i], val2[i], max_diff)
        elif isinstance(val1, set):
            for v in val1:
                self.assertIn(v, val2)
        elif isinstance(val1, dict):
            for k in val1:
                self.assertIn(k, val2)
                self.assertRecursiveAlmostEqual(val1[k], val2[k], max_diff)

    def test_slope_intercept_transform(self):
        """Test SlopeInterceptTransform with mx + b."""
        test_data = TEST_DATA.copy()
        expected_results = EXPECTED_RESULTS.copy()

        transform = SlopeInterceptTransform(
            input_field='input_field',
            output_field='output_field',
            m=1,
            b=1)

        while test_data:
            fields = test_data.pop(0)
            record = DASRecord(data_id='test', fields=fields)
            result = transform.transform(record)
            expected = expected_results.pop(0)
            logging.info('result: %s', result.fields)
            logging.info('expected: %s', expected)
            self.assertRecursiveAlmostEqual(result.fields, expected)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbosity', dest='verbosity',
                        default=0, action='count',
                        help='Increase output verbosity')
    args = parser.parse_args()

    LOGGING_FORMAT = '%(asctime)-15s %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(format=LOGGING_FORMAT)

    LOG_LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    args.verbosity = min(args.verbosity, max(LOG_LEVELS))
    logging.getLogger().setLevel(LOG_LEVELS[args.verbosity])

    unittest.main(warnings='ignore')
