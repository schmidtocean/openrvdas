#!/usr/bin/env python3
"""Compute true winds by processing and aggregating vessel
course/speed/heading and relative wind dir/speed records.

There are plenty of challenges with computing a universally-accepted
true wind value. Even with the correct algorithm (not a given), unless
the vessel nav and anemometer values have identical timestamps,
there's the question of how one integrates/interpolates/extrapolates
values with different timestamps.

The update_on_fields dict allows specifying which fields will trigger
a new computation. This allows making simplifying assumptions, e.g. that
vessel course/speed/heading is less variable than wind dir/speed, so we
will only produce updated results when we receive new anemometer records.
The max_field_age dict allows specifying a time beyond which we are unwilling
to trust any computations.

A more robust approach would be to wait until we got the next vessel
record and interpolate the course/speed/heading values between the two
vessel records (or, conversely, output when we got a vessel record,
using an interpolation of the preceding and following anemometer
readings?).

"""

import logging
import sys
import time

from pprint import pformat

from os.path import dirname, abspath
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from logger.utils.das_record import DASRecord, to_das_record_list  # noqa: E402
from logger.transforms.derived_data_transform import DerivedDataTransform  # noqa: E402

################################################################################
class WindDirCorrectionTransform(DerivedDataTransform):
    """Transform that computes a new wind direction based on a current wind
    direction and an offset.
    """

    def __init__(self,
                 wind_dir_field,
                 apparent_dir_name,
                 zero_line_reference=0,
                 data_id=None,
                 metadata_interval=None):
        """
        ```
        wind_dir_field
                 Data field to apply dir correction

        apparent_dir_name
                 Names that should be given to transform output values.

        zero_line_reference
                 Angle between bow and zero line on anemometer, referenced
                 to ship.

        metadata_interval - how many seconds between when we attach field metadata
                     to a record we send out.

        data_id  Optional name that will be attached to the resulting DASRecord
        ```
        """
        self.wind_dir_field = wind_dir_field

        self.apparent_dir_name = apparent_dir_name

        try:
            self.zero_line_reference = float(zero_line_reference)
        except:
            raise AttributeError('zero_line_reference must be a numeric value between 0.0 and 359.999')

        if self.zero_line_reference < 0 or self.zero_line_reference > 359.999:
            raise AttributeError('zero_line_reference must be a numeric value between 0.0 and 359.999')


        self.metadata_interval = metadata_interval
        self.last_metadata_send = 0

        self.data_id = data_id

        # TODO: It may make sense for us to cache most recent values so
        # that, for example, we can take single DASRecords in the
        # transform() method and use the most recent values we've seen
        # from previous calls.
        self.wind_dir_val = None

        self.wind_dir_val_time = 0

    ############################
    def fields(self):
        """Which fields are we interested in to produce transformed data?"""
        return [self.wind_dir_field]

    ############################
    def _metadata(self):
        """Return a dict of metadata for our derived fields."""

        metadata_fields = {
            self.apparent_dir_name: {
                'description': 'Derived apparent wind direction from %s, %s'
                % (self.wind_dir_field, self.zero_line_reference),
                'units': 'degrees',
                'device': 'WindDirCorrectionTransform',
                'device_type': 'DerivedWindDirCorrectionTransform',
                'device_type_field': self.apparent_dir_name
            }
        }
        return metadata_fields

    ############################
    def transform(self, record):
        """Incorporate any useable fields in this record, and if it gives
        us a new true wind value, return the results."""

        if record is None:
            return None

        # If we've got a list, hope it's a list of records. Recurse,
        # calling transform() on each of the list elements in order and
        # return the resulting list.
        if type(record) is list:
            results = []
            for single_record in record:
                results.append(self.transform(single_record))
            return results

        results = []
        for das_record in to_das_record_list(record):

            timestamp = das_record.timestamp
            if not timestamp:
                logging.info('DASRecord is missing timestamp - skipping')
                continue

            # Get latest values for any of our fields
            fields = das_record.fields

            if self.wind_dir_field in fields:
                if timestamp >= self.wind_dir_val_time:
                    self.wind_dir_val = fields.get(self.wind_dir_field)
                    self.wind_dir_val_time = timestamp

            apparent_dir = (self.wind_dir_val+self.zero_line_reference) % 360
            logging.debug('Corrected apparent wind: %s', apparent_dir)
            
            # Add in metadata if so specified and it's been long enough since
            # we last sent it.
            now = time.time()
            if self.metadata_interval and \
               now - self.metadata_interval > self.last_metadata_send:
                metadata = {'fields': self._metadata()}
                self.last_metadata_send = now
                logging.debug('Emitting metadata: %s', pformat(metadata))
            else:
                metadata = None

            results.append(DASRecord(timestamp=timestamp, fields={self.apparent_dir_name: apparent_dir},
                                     metadata=metadata, data_id=self.data_id))

        logging.debug('Sending %d corrected wind direction results.', len(results))
        return results
