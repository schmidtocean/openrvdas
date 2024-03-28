#!/usr/bin/env python3

# flake8: noqa E501  - don't worry about long lines in sample data

import logging
import sys
import unittest

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from logger.utils.das_record import DASRecord  # noqa: E402
from local.soi.modules.transforms.winddircorrection_transform import WindDirCorrectionTransform  # noqa: E402

SANITY_CHECK = [
    {
        'RelWindDir': 0,
    },
    {
        'RelWindDir': 180,
    },
    {
        'RelWindDir': 90,
    },
]

SANITY_RESULTS = [
    {
        'PortApparentWindDir': 0,
    },
    {
        'PortApparentWindDir': 180,
    },
    {
        'PortApparentWindDir': 90,
    },
]

OFFSET_RESULTS = [
    {
        'PortApparentWindDir': 180,
    },
    {
        'PortApparentWindDir': 0,
    },
    {
        'PortApparentWindDir': 270,
    },
]

class TestWindDirCorrectionTransform(unittest.TestCase):
    ############################
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
    def test_sanity(self):
        """Sanity check that the numbers coming out make sense."""
        check = SANITY_CHECK.copy()
        expected_results = SANITY_RESULTS.copy()

        wdc = WindDirCorrectionTransform(
            wind_dir_field='RelWindDir',
            apparent_dir_name='PortApparentWindDir')

        while check:
            fields = check.pop(0)
            record = DASRecord(data_id='wdc', fields=fields)
            result = wdc.transform(record)
            if type(result) is list:
                if len(result):
                    result = result[0]
                else:
                    result is None
            expected = expected_results.pop(0)
            logging.info('sanity result: %s', result.fields)
            logging.info('sanity expected: %s', expected)
            self.assertRecursiveAlmostEqual(result.fields, expected)

        return

    ############################
    def test_offset(self):
        """Sanity check that the numbers coming out make sense."""
        check = SANITY_CHECK.copy()
        expected_results = OFFSET_RESULTS.copy()

        wdc = WindDirCorrectionTransform(
            wind_dir_field='RelWindDir',
            zero_line_reference=180,
            apparent_dir_name='PortApparentWindDir')

        while check:
            fields = check.pop(0)
            record = DASRecord(data_id='wdc', fields=fields)
            result = wdc.transform(record)
            if type(result) is list:
                if len(result):
                    result = result[0]
                else:
                    result is None
            expected = expected_results.pop(0)
            logging.info('offset result: %s', result.fields)
            logging.info('offset expected: %s', expected)
            self.assertRecursiveAlmostEqual(result.fields, expected)

        return


################################################################################
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
