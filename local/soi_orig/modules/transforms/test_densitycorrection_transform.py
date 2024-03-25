#!/usr/bin/env python3

import sys
import numpy
import logging
import unittest

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from local.soi.modules.transforms.densitycorrection_transform import DensityCorrectionTransform  # noqa: E402
from logger.utils.das_record import DASRecord  # noqa: E402
from logger.transforms.parse_transform import ParseTransform  # noqa: E402

LINES = """sb_pilot_choice 2021-08-01T16:20:00.072000Z $GPGGA,162000.03,3306.09892353,N,11753.01678546,W,-1,0,0.0,527.364,M,0.000,M,0.0,*7D
sb_ctd_svx2 2021-08-01T16:20:00.105000Z $CTD,34.86,6.6200,769.11,533.9594,34.6510,1484.89
sb_pilot_choice 2021-08-01T16:20:00.326000Z $GPGGA,162000.31,3306.09892102,N,11753.01678043,W,-1,0,0.0,527.364,M,0.000,M,0.0,*7A
sb_pilot_choice 2021-08-01T16:20:00.576000Z $GPGGA,162000.55,3306.09891851,N,11753.01677540,W,-1,0,0.0,527.364,M,0.000,M,0.0,*7D
sb_ctd_svx2 2021-08-01T16:20:00.607000Z $CTD,34.85,6.6200,769.06,533.9221,34.6470,1484.88
sb_pilot_choice 2021-08-01T16:20:00.826000Z $GPGGA,162000.81,3306.09891599,N,11753.01676534,W,-1,0,0.0,527.364,M,0.000,M,0.0,*7F
sb_pilot_choice 2021-08-01T16:20:01.076000Z $GPGGA,162001.03,3306.09891599,N,11753.01677037,W,-1,0,0.0,527.364,M,0.000,M,0.0,*73
sb_ctd_svx2 2021-08-01T16:20:01.107000Z $CTD,34.86,6.6150,769.03,533.9000,34.6540,1484.99
sb_pilot_choice 2021-08-01T16:20:01.357000Z $GPGGA,162001.30,3306.09891348,N,11753.01676031,W,-1,0,0.0,527.351,M,0.000,M,0.0,*78
sb_ctd_svx2 2021-08-01T16:20:01.607000Z $CTD,34.86,6.6160,769.01,533.8899,34.6530,1485.03
sb_pilot_choice 2021-08-01T16:20:01.607000Z $GPGGA,162001.59,3306.09890845,N,11753.01675528,W,-1,0,0.0,527.351,M,0.000,M,0.0,*7E
sb_pilot_choice 2021-08-01T16:20:01.857000Z $GPGGA,162001.83,3306.09890593,N,11753.01675025,W,-1,0,0.0,527.351,M,0.000,M,0.0,*77
sb_ctd_svx2 2021-08-01T16:20:02.107000Z $CTD,34.86,6.6200,769.01,533.8909,34.6490,1485.05
sb_pilot_choice 2021-08-01T16:20:02.107000Z $GPGGA,162002.06,3306.09890593,N,11753.01674522,W,-1,0,0.0,527.351,M,0.000,M,0.0,*7A
sb_pilot_choice 2021-08-01T16:20:02.371000Z $GPGGA,162002.31,3306.09890090,N,11753.01674020,W,-1,0,0.0,527.316,M,0.000,M,0.0,*7C
sb_ctd_svx2 2021-08-01T16:20:02.621000Z $CTD,34.86,6.6210,769.06,533.9201,34.6520,1485.02
sb_pilot_choice 2021-08-01T16:20:02.621000Z $GPGGA,162002.59,3306.09889839,N,11753.01673517,W,-1,0,0.0,527.316,M,0.000,M,0.0,*77
sb_pilot_choice 2021-08-01T16:20:02.871000Z $GPGGA,162002.82,3306.09889587,N,11753.01673014,W,-1,0,0.0,527.316,M,0.000,M,0.0,*7F
sb_ctd_svx2 2021-08-01T16:20:03.119000Z $CTD,34.87,6.6230,769.01,533.8899,34.6550,1484.98
sb_pilot_choice 2021-08-01T16:20:03.150000Z $GPGGA,162003.10,3306.09889336,N,11753.01672511,W,-1,0,0.0,527.316,M,0.000,M,0.0,*78
sb_pilot_choice 2021-08-01T16:20:03.402000Z $GPGGA,162003.34,3306.09889084,N,11753.01672008,W,-1,0,0.0,527.303,M,0.000,M,0.0,*7D
sb_ctd_svx2 2021-08-01T16:20:03.620000Z $CTD,34.87,6.6240,768.98,533.8698,34.6580,1485.00
sb_pilot_choice 2021-08-01T16:20:03.651000Z $GPGGA,162003.60,3306.09888833,N,11753.01671505,W,-1,0,0.0,527.303,M,0.000,M,0.0,*72
sb_pilot_choice 2021-08-01T16:20:03.902000Z $GPGGA,162003.82,3306.09888330,N,11753.01671002,W,-1,0,0.0,527.303,M,0.000,M,0.0,*74
sb_ctd_svx2 2021-08-01T16:20:04.120000Z $CTD,34.87,6.6190,769.01,533.8869,34.6660,1485.04
sb_pilot_choice 2021-08-01T16:20:04.151000Z $GPGGA,162004.14,3306.09888079,N,11753.01671002,W,-1,0,0.0,527.303,M,0.000,M,0.0,*72
sb_pilot_choice 2021-08-01T16:20:04.401000Z $GPGGA,162004.38,3306.09887827,N,11753.01670499,W,-1,0,0.0,527.316,M,0.000,M,0.0,*73
sb_ctd_svx2 2021-08-01T16:20:04.620000Z $CTD,34.88,6.6120,769.06,533.9242,34.6810,1485.15
sb_pilot_choice 2021-08-01T16:20:04.682000Z $GPGGA,162004.62,3306.09887576,N,11753.01669996,W,-1,0,0.0,527.316,M,0.000,M,0.0,*7F
sb_pilot_choice 2021-08-01T16:20:04.933000Z $GPGGA,162004.90,3306.09887324,N,11753.01669996,W,-1,0,0.0,527.316,M,0.000,M,0.0,*73
sb_ctd_svx2 2021-08-01T16:20:05.120000Z $CTD,34.87,6.6160,769.13,533.9695,34.6680,1485.17
sb_pilot_choice 2021-08-01T16:20:05.182000Z $GPGGA,162005.14,3306.09887073,N,11753.01669493,W,-1,0,0.0,527.344,M,0.000,M,0.0,*70
sb_pilot_choice 2021-08-01T16:20:05.446000Z $GPGGA,162005.42,3306.09886821,N,11753.01668990,W,-1,0,0.0,527.344,M,0.000,M,0.0,*72
sb_ctd_svx2 2021-08-01T16:20:05.603000Z $CTD,34.87,6.6300,769.09,533.9443,34.6520,1485.15
sb_pilot_choice 2021-08-01T16:20:05.696000Z $GPGGA,162005.68,3306.09886570,N,11753.01668990,W,-1,0,0.0,527.344,M,0.000,M,0.0,*73
sb_pilot_choice 2021-08-01T16:20:05.946000Z $GPGGA,162005.92,3306.09886570,N,11753.01668990,W,-1,0,0.0,527.344,M,0.000,M,0.0,*76
sb_ctd_svx2 2021-08-01T16:20:06.103000Z $CTD,34.87,6.6430,769.12,533.9654,34.6420,1485.14
sb_pilot_choice 2021-08-01T16:20:06.194000Z $GPGGA,162006.18,3306.09886318,N,11753.01668487,W,-1,0,0.0,527.344,M,0.000,M,0.0,*74
sb_pilot_choice 2021-08-01T16:20:06.446000Z $GPGGA,162006.41,3306.09885816,N,11753.01667985,W,-1,0,0.0,527.385,M,0.000,M,0.0,*73
sb_ctd_svx2 2021-08-01T16:20:06.602000Z $CTD,34.88,6.6500,769.12,533.9664,34.6430,1485.19
sb_pilot_choice 2021-08-01T16:20:06.727000Z $GPGGA,162006.67,3306.09885564,N,11753.01667482,W,-1,0,0.0,527.385,M,0.000,M,0.0,*75
sb_pilot_choice 2021-08-01T16:20:06.977000Z $GPGGA,162006.94,3306.09885313,N,11753.01666979,W,-1,0,0.0,527.385,M,0.000,M,0.0,*77
sb_ctd_svx2 2021-08-01T16:20:07.102000Z $CTD,34.88,6.6550,769.09,533.9413,34.6450,1485.16
sb_pilot_choice 2021-08-01T16:20:07.227000Z $GPGGA,162007.22,3306.09885061,N,11753.01666476,W,-1,0,0.0,527.398,M,0.000,M,0.0,*73
sb_pilot_choice 2021-08-01T16:20:07.477000Z $GPGGA,162007.44,3306.09884810,N,11753.01665973,W,-1,0,0.0,527.398,M,0.000,M,0.0,*77
sb_ctd_svx2 2021-08-01T16:20:07.602000Z $CTD,34.89,6.6520,769.11,533.9554,34.6530,1485.16
sb_pilot_choice 2021-08-01T16:20:07.758000Z $GPGGA,162007.71,3306.09884558,N,11753.01665470,W,-1,0,0.0,527.398,M,0.000,M,0.0,*7E
sb_pilot_choice 2021-08-01T16:20:08.008000Z $GPGGA,162007.98,3306.09884307,N,11753.01664967,W,-1,0,0.0,527.398,M,0.000,M,0.0,*7F
sb_ctd_svx2 2021-08-01T16:20:08.102000Z $CTD,34.89,6.6560,769.14,533.9785,34.6490,1485.16
sb_pilot_choice 2021-08-01T16:20:08.258000Z $GPGGA,162008.22,3306.09884055,N,11753.01664464,W,-1,0,0.0,527.398,M,0.000,M,0.0,*7B
sb_pilot_choice 2021-08-01T16:20:08.523000Z $GPGGA,162008.48,3306.09884055,N,11753.01664464,W,-1,0,0.0,527.398,M,0.000,M,0.0,*77
sb_ctd_svx2 2021-08-01T16:20:08.617000Z $CTD,34.89,6.6560,769.15,533.9876,34.6490,1485.08
sb_pilot_choice 2021-08-01T16:20:08.773000Z $GPGGA,162008.75,3306.09884055,N,11753.01663961,W,-1,0,0.0,527.398,M,0.000,M,0.0,*76
sb_pilot_choice 2021-08-01T16:20:09.023000Z $GPGGA,162008.98,3306.09884055,N,11753.01663961,W,-1,0,0.0,527.398,M,0.000,M,0.0,*75
sb_ctd_svx2 2021-08-01T16:20:09.117000Z $CTD,34.88,6.6580,769.17,534.0017,34.6420,1485.07
sb_pilot_choice 2021-08-01T16:20:09.275000Z $GPGGA,162009.27,3306.09884055,N,11753.01663961,W,-1,0,0.0,527.412,M,0.000,M,0.0,*75
sb_pilot_choice 2021-08-01T16:20:09.527000Z $GPGGA,162009.51,3306.09884055,N,11753.01663458,W,-1,0,0.0,527.412,M,0.000,M,0.0,*73
sb_ctd_svx2 2021-08-01T16:20:09.621000Z $CTD,34.88,6.6500,769.24,534.0450,34.6430,1485.05""".split('\n')

RESULTS = [
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.64},
    None,
    None,
    {'Density_Corr': 1029.65},
    None,
    None,
    {'Density_Corr': 1029.64},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.62},
    None,
    None,
    {'Density_Corr': 1029.62},
    None,
    None,
    {'Density_Corr': 1029.62},
    None,
    None,
    {'Density_Corr': 1029.63},
    None,
    None,
    {'Density_Corr': 1029.62},
    None,
    None,
    {'Density_Corr': 1029.62},
    None,
    None,
    {'Density_Corr': 1029.62},
    None,
    None,
    {'Density_Corr': 1029.62}
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
        dc = DensityCorrectionTransform(corr_density_name='Density_Corr',
                                        salinity_field='Salinity',
                                        temperature_field='WaterTemp',
                                        pressure_field='WaterPres',
                                        latitude_field='Latitude',
                                        longitude_field='Longitude',
                                        pressure_coefficient=0.689475728)

        self.assertIsNone(dc.transform(None))

    ############################
    def test_default(self):
        lines = LINES.copy()
        expected_results = RESULTS.copy()

        dc = DensityCorrectionTransform(corr_density_name='Density_Corr',
                                        salinity_field='Salinity',
                                        temperature_field='WaterTemp',
                                        pressure_field='WaterPres',
                                        latitude_field='Latitude',
                                        longitude_field='Longitude',
                                        pressure_coefficient=0.689475728,
                                        update_on_fields=['WaterPres'])

        parse = ParseTransform(
            field_patterns=[
                '$CTD,{Conductivity:g},{WaterTemp:g},{WaterPres:g},{Depth:g},{Salinity:g},{SoundVelocity:g}',
                '$GPGGA,{GPSTime:f},{Latitude:nlat_dir},{Longitude:nlat_dir},{FixQuality:d},{NumSats:d},{HDOP:of},{AntennaHeight:of},M,{GeoidHeight:of},M,{LastDGPSUpdate:of},{DGPSStationID:od}*{CheckSum:x}'
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
