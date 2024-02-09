#!/usr/bin/env python3
"""
"""

import sys
from copy import deepcopy
import logging
import unittest

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from local.soi.modules.transforms.slopecorrection_transform import SlopeCorrectionTransform  # noqa: E402

RECORDS = [
    {'data_id': 'gyr1', 'message_type': '$HEROT',
     'timestamp': 1510275607.737000,
     'fields': {'HeadingTrue': 90, 'RateOfTurn': 2.9}, 'metadata': {}
    }
]

RESULTS = [
     {'HeadingTrue': 90, 'RateOfTurn': 2.9}
]

RESULTS_1 = [
     {'HeadingTrue': 99, 'RateOfTurn': 2.9}
]

RESULTS_2 = [
     {'HeadingTrue': 95, 'RateOfTurn': 2.9}
]

RESULTS_3 = [
     {'HeadingTrue': 104, 'RateOfTurn': 2.9}
]

class TestSlopeCorrectionTransform(unittest.TestCase):
    """
    """

    def assertRecursiveAlmostEqual(self, val1, val2, max_diff=0.00001):
        """Assert that two values/dicts/lists/sets are almost equal. That is,
        that their non-numerical entries are equal, and that their
        numerical entries are equal to within max_diff. NOTE: does not
        detect 'almost' equal for sets.
        """
        if type(val1) in (int, float) and type(val2) in (int, float):
            self.assertLess(abs(val1-val2), max_diff)
            return

        if type(val1) in (str, bool, type(None)):
            self.assertEqual(val1, val2)
            return

        # If here, it should be a list, set or dict
        self.assertTrue(type(val1) in (set, list, dict))
        self.assertEqual(type(val1), type(val2))
        self.assertEqual(len(val1), len(val2))

        if type(val1) == list:
            for i in range(len(val1)):
                self.assertRecursiveAlmostEqual(val1[i], val2[i], max_diff)

        elif type(val1) == set:
            for v in val1:
                self.assertTrue(v in val2)

        elif type(val1) == dict:
            for k in val1:
                self.assertTrue(k in val2)
                self.assertRecursiveAlmostEqual(val1[k], val2[k], max_diff)


    ############################
    def test_no_record(self):
        sc = SlopeCorrectionTransform(None)

        self.assertIsNone(sc.transform(None))



    ############################
    def test_default(self):
        records = deepcopy(RECORDS)
        expected_results = RESULTS.copy()

        sc = SlopeCorrectionTransform(None)

        #while records:
        #    record = sc.transform(records.pop(0))

        result_list = sc.transform(records)
        self.assertEqual(type(result_list), list)
        #result = result_list[0] if len(result_list) else None

        while expected_results:

            expected = expected_results.pop(0)
            result = result_list.pop(0) if len(result_list) else None
            logging.debug('Got result: %s', result)
            logging.debug('Expected result: %s\n', expected)

            if not result or not expected:
                self.assertIsNone(result)
                self.assertIsNone(expected)
            else:
                logging.debug('Comparing result:\n%s\nwith expected:\n%s',
                              result['fields'], expected)
                self.assertRecursiveAlmostEqual(result['fields'], expected)

    ############################
    def test_slope(self):
        records = deepcopy(RECORDS)
        expected_results = RESULTS_1.copy()

        sc = SlopeCorrectionTransform('HeadingTrue:1.1:')

        result_list = sc.transform(records)
        self.assertEqual(type(result_list), list)

        while expected_results:

            expected = expected_results.pop(0)
            result = result_list.pop(0) if len(result_list) else None
            logging.debug('Got result: %s', result)
            logging.debug('Expected result: %s\n', expected)

            if not result or not expected:
                self.assertIsNone(result)
                self.assertIsNone(expected)
            else:
                logging.debug('Comparing result:\n%s\nwith expected:\n%s',
                              result['fields'], expected)
                self.assertRecursiveAlmostEqual(result['fields'], expected)

    ############################
    def test_offset(self):
        records = deepcopy(RECORDS)
        expected_results = RESULTS_2.copy()

        sc = SlopeCorrectionTransform(slopes='HeadingTrue::5')

        result_list = sc.transform(records)
        self.assertEqual(type(result_list), list)

        while expected_results:

            expected = expected_results.pop(0)
            result = result_list.pop(0) if len(result_list) else None
            logging.debug('Got result: %s', result)
            logging.debug('Expected result: %s\n', expected)

            if not result or not expected:
                self.assertIsNone(result)
                self.assertIsNone(expected)
            else:
                logging.debug('Comparing result:\n%s\nwith expected:\n%s',
                              result['fields'], expected)
                self.assertRecursiveAlmostEqual(result['fields'], expected)


    ############################
    def test_slope_offset(self):
        records = deepcopy(RECORDS)
        expected_results = RESULTS_3.copy()

        sc = SlopeCorrectionTransform(slopes='HeadingTrue:1.1:5')

        result_list = sc.transform(records)
        self.assertEqual(type(result_list), list)

        while expected_results:

            expected = expected_results.pop(0)
            result = result_list.pop(0) if len(result_list) else None
            logging.debug('Got result: %s', result)
            logging.debug('Expected result: %s\n', expected)

            if not result or not expected:
                self.assertIsNone(result)
                self.assertIsNone(expected)
            else:
                logging.debug('Comparing result:\n%s\nwith expected:\n%s',
                              result['fields'], expected)
                self.assertRecursiveAlmostEqual(result['fields'], expected)

if __name__ == '__main__':
    unittest.main()
