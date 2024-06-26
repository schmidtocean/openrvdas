#!/usr/bin/env python3
"""
TODO: option to initialize with a message to be output in case of failure.

TODO: option to intialize with a flag saying whether records will be
DASRecords or dictionary, or...?

"""

import logging
import sys

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
#from logger.utils import formats  # noqa: E402
from logger.utils.das_record import DASRecord  # noqa: E402
from logger.transforms.transform import Transform  # noqa: E402

################################################################################
#
class SlopeCorrectionTransform(Transform):
    """
    Transform that filters out values in a passed DASRecord that are out of slopes."""

    def __init__(self, slopes, log_level=logging.INFO):
        """
        ```
        slopes
                 A comma-separated list of conditions of the format

                    <field_name>:<slope>:<offset>

                 Either <slope> or <offset> may be empty. For example:
                    # No slope, no offset
                    'SeawaterTemp::22.4,SpeedOverGround:1.05:,SpeedThroughWater:1.09:5.25'

        log_level
                 At what level the transform should log a message when it sees a value
                 that is out of bounds. Allowed values are log levels from the logging module,
                 e.g. logging.INFO, logging.DEBUG, logging.WARNING, etc.

                 If the logger is running in normal mode, it will display messages that
                 have log level INFO and more severe (WARNING, ERROR, FATAL). Setting the
                 log_level parameter of this transform to logging.WARNING means that any time
                 a value falls out of its specified bounds, a WARNING message will be sent to
                 the console, appearing in yellow on the web console. logging.ERROR means it will
                 appear in red. Setting it to logging.DEBUG means that no message will appear on
                 the console.

        ```
        """
        self.slopes = {}

        if slopes is not None:
            for condition in slopes.split(','):
                try:
                    (var, slope_str, offset_str) = condition.split(':')
                    slope = 1 if slope_str == '' else float(slope_str)
                    offset = 0 if offset_str == '' else float(offset_str)
                    self.slopes[var] = (slope, offset)
                except ValueError:
                    raise ValueError('SlopeCorrectionTransform slopes must be colon-separated '
                                 'triples of field_name:slope:offset. '
                                 f'Found "{condition}" instead.')

        if log_level not in [logging.DEBUG, logging.INFO, logging.WARNING,
                             logging.ERROR, logging.FATAL]:
            raise ValueError('SlopeCorrectionTransform log_level must be a logging module log '
                             'level, such as logging.DEBUG, logging.INFO or logging.WARNING. '
                             f'Found "{log_level}" instead.')
        self.log_level = log_level

    ############################
    def transform(self, record):
        """Does record violate any bounds?"""
        if not record:
            return None

        # If we've got a list, hope it's a list of records. Recurse,
        # calling transform() on each of the list elements in order and
        # return the resulting list.
        if isinstance(record,list):
            results = []
            for single_record in record:
                results.append(self.transform(single_record))
            return results

        if isinstance(record, DASRecord):
            fields = record.fields
        elif isinstance(record, dict):
            if 'fields' in record:
                fields = record['fields']
            else:
                fields = record
        else:
            logging.log(self.log_level,
                        'Record passed to SlopeCorrectionTransform was neither a dict nor a '
                        'DASRecord. Type was %s: %s', type(record), str(record)[:80])
            return None

        for mxb in self.slopes:
            if mxb not in fields:
                continue
            (slope, offset) = self.slopes[mxb]  # what are the slope/offset mxbs?

            value = fields.get(mxb)  # what is the record's value of this field?

            # We expect field value to be numeric; if not, complain lightly and remove it
            if not isinstance(value, int) and not isinstance(value, float):
                logging.log(self.log_level,
                        'SlopeCorrectionTransform found non-numeric value for %s: %s', mxb, value)
                del fields[mxb]
                continue

            fields[mxb] = value * slope + offset

        return record
