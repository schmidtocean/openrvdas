import logging
import sys
import time
import unittest

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from local.soi.modules.readers.moxa_iologik_e12xx_reader import MOXAioLogikE12xxReader  # noqa: E402

from logger.utils import timestamp  # noqa: E402
from logger.readers.logfile_reader import LogfileReader  # noqa: E402

class TestMOXAioLogikE12xxReader(unittest.TestCase):

    ############################
    def test_no_device(self):
        '''
        Test when there is no device at the configured address
        '''
        def create_bad_reader():
            return MOXAioLogikE12xxReader(address='10.10.10.42')

        self.assertRaises(AttributeError, create_bad_reader)


    ############################
    def test_default_device(self):
        '''
        Test when there is a connected device at the configured address
        '''
        # moxa_reader = MOXAioLogikE12xxReader(address='10.23.10.45', analog_channels='0,1')
        moxa_reader = MOXAioLogikE12xxReader(address='10.23.10.45')


        record = moxa_reader.read()
        logging.debug(record)

        self.assertIsInstance(record,list)
        self.assertEqual(len(record), 4)

        single_record = record[0].split(',')
        self.assertIn(single_record[0],['0','1','2','3'])
        self.assertIn(single_record[1],['0','1'])
        self.assertTrue(int(single_record[2]) >= 0)
        self.assertTrue(float(single_record[3]) >= 0.0)

################################################################################
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbosity', dest='verbosity',
                        default=0, action='count',
                        help='Increase output verbosity')
    args = parser.parse_args()

    LOGGING_FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=LOGGING_FORMAT)

    LOG_LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    args.verbosity = min(args.verbosity, max(LOG_LEVELS))
    logging.getLogger().setLevel(LOG_LEVELS[args.verbosity])

    unittest.main(warnings='ignore')
