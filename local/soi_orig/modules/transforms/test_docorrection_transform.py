#!/usr/bin/env python3

import sys
import numpy
import logging
import unittest

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from local.soi.modules.transforms.docorrection_transform import DOCorrectionTransform  # noqa: E402
from logger.utils.das_record import DASRecord  # noqa: E402
from logger.transforms.parse_transform import ParseTransform  # noqa: E402

LINES = """sb_ctd_svx2 2021-08-01T16:20:00.105000Z $CTD,34.86,6.6200,769.11,533.9594,34.6510,1484.89
sb_o2 2021-08-01T16:20:00.455000Z $O2,9.814,2.502,5.66,4831,582,61.917,61.917,69.985,8.068,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:00.607000Z $CTD,34.85,6.6200,769.06,533.9221,34.6470,1484.88
sb_ctd_svx2 2021-08-01T16:20:01.107000Z $CTD,34.86,6.6150,769.03,533.9000,34.6540,1484.99
sb_o2 2021-08-01T16:20:01.454000Z $O2,9.826,2.506,5.662,4831,582,61.915,61.915,69.984,8.069,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:01.607000Z $CTD,34.86,6.6160,769.01,533.8899,34.6530,1485.03
sb_ctd_svx2 2021-08-01T16:20:02.107000Z $CTD,34.86,6.6200,769.01,533.8909,34.6490,1485.05
sb_o2 2021-08-01T16:20:02.437000Z $O2,9.826,2.506,5.662,4831,582,61.915,61.915,69.984,8.069,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:02.621000Z $CTD,34.86,6.6210,769.06,533.9201,34.6520,1485.02
sb_ctd_svx2 2021-08-01T16:20:03.119000Z $CTD,34.87,6.6230,769.01,533.8899,34.6550,1484.98
sb_o2 2021-08-01T16:20:03.436000Z $O2,9.826,2.506,5.662,4831,582,61.915,61.915,69.984,8.069,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:03.620000Z $CTD,34.87,6.6240,768.98,533.8698,34.6580,1485.00
sb_ctd_svx2 2021-08-01T16:20:04.120000Z $CTD,34.87,6.6190,769.01,533.8869,34.6660,1485.04
sb_o2 2021-08-01T16:20:04.436000Z $O2,9.805,2.5,5.662,4831,582,61.918,61.918,69.985,8.067,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:04.620000Z $CTD,34.88,6.6120,769.06,533.9242,34.6810,1485.15
sb_ctd_svx2 2021-08-01T16:20:05.120000Z $CTD,34.87,6.6160,769.13,533.9695,34.6680,1485.17
sb_o2 2021-08-01T16:20:05.450000Z $O2,9.805,2.5,5.662,4831,582,61.918,61.918,69.985,8.067,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:05.603000Z $CTD,34.87,6.6300,769.09,533.9443,34.6520,1485.15
sb_ctd_svx2 2021-08-01T16:20:06.103000Z $CTD,34.87,6.6430,769.12,533.9654,34.6420,1485.14
sb_o2 2021-08-01T16:20:06.450000Z $O2,9.805,2.5,5.662,4831,582,61.918,61.918,69.985,8.067,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:06.602000Z $CTD,34.88,6.6500,769.12,533.9664,34.6430,1485.19
sb_ctd_svx2 2021-08-01T16:20:07.102000Z $CTD,34.88,6.6550,769.09,533.9413,34.6450,1485.16
sb_o2 2021-08-01T16:20:07.449000Z $O2,9.811,2.502,5.662,4831,582,61.917,61.917,69.985,8.068,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:07.602000Z $CTD,34.89,6.6520,769.11,533.9554,34.6530,1485.16
sb_ctd_svx2 2021-08-01T16:20:08.102000Z $CTD,34.89,6.6560,769.14,533.9785,34.6490,1485.16
sb_o2 2021-08-01T16:20:08.449000Z $O2,9.811,2.502,5.662,4831,582,61.917,61.917,69.985,8.068,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:08.617000Z $CTD,34.89,6.6560,769.15,533.9876,34.6490,1485.08
sb_ctd_svx2 2021-08-01T16:20:09.117000Z $CTD,34.88,6.6580,769.17,534.0017,34.6420,1485.07
sb_o2 2021-08-01T16:20:09.464000Z $O2,9.811,2.502,5.662,4831,582,61.917,61.917,69.985,8.068,957.1,668.3
sb_ctd_svx2 2021-08-01T16:20:09.621000Z $CTD,34.88,6.6500,769.24,534.0450,34.6430,1485.05""".split('\n')

RESULTS = [
    None,
    {'Concentration_Corr': 7.96, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.96, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.96, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.96, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.95, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.95, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.95, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.95, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.95, 'Saturation_Corr': 2.61},
    None,
    None,
    {'Concentration_Corr': 7.95, 'Saturation_Corr': 2.61},
    None
]

class TestDensityCorrectionTransform(unittest.TestCase):

    ############################
    def assertRecursiveAlmostEqual(self, val1, val2, max_diff=0.00001):
        """Assert that two values/dicts/lists/sets are almost equal. That is,
        that their non-numerical entries are equal, and that their
        numerical entries are equal to within max_diff. NOTE: does not
        detect 'almost' equal for sets.
        """
        if type(val1) in (int, float, numpy.float64) and type(val2) in (int, float, numpy.float64):
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
        dc = DOCorrectionTransform(conc_field='Concentration',
                                    temp_field='WaterTemp',
                                    sal_field='Salinity',
                                    depth_field='Depth',
                                    corr_conc_name='Concentration_Corr',
                                    corr_sat_name='Saturation_Corr',
                                    update_on_fields=['Concentration'])

        self.assertIsNone(dc.transform(None))

    ############################
    def test_default(self):
        lines = LINES.copy()
        expected_results = RESULTS.copy()

        dc = DOCorrectionTransform(conc_field='Concentration',
                                    temp_field='WaterTemp',
                                    sal_field='Salinity',
                                    depth_field='Depth',
                                    corr_conc_name='Concentration_Corr',
                                    corr_sat_name='Saturation_Corr',
                                    update_on_fields=['Concentration'])
        parse = ParseTransform(
            field_patterns=[
                '$CTD,{Conductivity:g},{WaterTemp:g},{WaterPres:g},{Depth:g},{Salinity:g},{SoundVelocity:g}',
                # $O2,49.49,13.288,7.723,4831,582,56.039,56.039,64.212,8.173,883,651.5
                '$O2,{Concentration:og},{Saturation:og},{Temperature:og},{Measurement_1:og},{Measurement_2:og},{CalPhase:og},{TCPhase:og},{C1_RPH:og},{C2_RPH:og},{C1_AMP:og},{C2_AMP:og}'
            ])

        while lines:
            record = parse.transform(lines.pop(0))
            result_list = dc.transform(record)
            self.assertEqual(type(result_list), list)
            result = result_list[0] if len(result_list) else None

            expected = expected_results.pop(0)
            logging.debug('Got result: %s', result)
            logging.debug('Expected result: %s\n', expected)

            if not result or not expected:
                self.assertIsNone(result)
                self.assertIsNone(expected)
            else:
                logging.debug('Comparing result:\n%s\nwith expected:\n%s',
                              result.fields, expected)
                self.assertRecursiveAlmostEqual(result.fields, expected)


if __name__ == '__main__':
    unittest.main()
