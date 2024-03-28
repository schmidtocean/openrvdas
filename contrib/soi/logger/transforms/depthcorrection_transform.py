#!/usr/bin/env python3

import sys
import time
import logging
import gsw

from os.path import dirname, realpath
sys.path.append(dirname(dirname(dirname(dirname(realpath(__file__))))))
from logger.utils.das_record import DASRecord, to_das_record_list  # noqa: E402
from logger.transforms.derived_data_transform import DerivedDataTransform  # noqa: E402


################################################################################
#
class DepthCorrectionTransform(DerivedDataTransform):
    """Perform the conversion and add the applicable fields to the DASRecord or
    dict.
    """

    def __init__(self,
                 corr_depth_name,
                 latitude_field,
                 depth_field=None,
                 pressure_field=None,
                 pressure_abs=False,
                 conv_coefficient=1,
                 update_on_fields=[],
                 max_field_age={},
                 metadata_interval=None):

        """
        ```
        depth_field,
        latitude_field,
        pressure_field
                 Field names from which we should take values for
                 pressure OR depth.

        pressure_abs pressure provided is absolute vs relative sealevel,
                 default: false

        corr_depth_name
                 Names that should be given to transform output values.

        conv_coefficient
                 multiply the depth or pressure by the coefficient to convert
                 to dbar

        update_on_fields
                 If non-empty, a list of fields, any of whose arrival should
                 trigger an output record. If None, generate output when any
                 field is updated.

        max_field_age
                 If non-empty, a dict of field_name:seconds, specifying that
                 no output is to be produces if the age of any of the specified
                 names is older than the specified number of seconds.

        metadata_interval - how many seconds between when we attach field metadata
                     to a record we send out.
        ```
        """

        if depth_field is not None and pressure_field is not None:
            raise ValueError("Cannot declare a pressure_field AND depth_field")

        if conv_coefficient == 0:
            raise ValueError("conv_coefficient cannot be zero (0)")

        self.latitude_field = latitude_field
        self.pressure_field = pressure_field if pressure_field is not None else depth_field
        self.pressure_abs = pressure_abs
        self.conv_coefficient = conv_coefficient
        self.corr_depth_name = corr_depth_name

        self.update_on_fields = update_on_fields
        self.max_field_age = max_field_age
        self.field_age = {}

        self.metadata_interval = metadata_interval
        self.last_metadata_send = 0

        self.latitude_val = None
        self.latitude_val_time = 0
        self.pressure_val = None
        self.pressure_val_time = 0

    ############################
    def fields(self):
        """Which fields are we interested in to produce transformed data?"""
        return [self.pressure_field]

    ############################
    def _metadata(self):
        """Return a dict of metadata for our derived fields."""

        metadata_fields = {
            self.corr_depth_name: {
                'description': 'Derived depth correction from %s'
                % (self.pressure_field),
                'units': 'm',
                'device': 'DepthCorrectionTransform',
                'device_type': 'DerivedDepthCorrectionTransform',
                'device_type_field': self.corr_depth_name
            }
        }
        return metadata_fields

    ############################
    @staticmethod
    def depth_correction(pressure, latitude):

        """
        calculated corrected depth values
        """

        corr_depth = gsw.z_from_p(pressure, latitude,
                                  geo_strf_dyn_height=0,
                                  sea_surface_geopotential=0)
        corr_depth = round(abs(corr_depth), 2)
        logging.debug('Corrected Depth: %s', corr_depth)

        return corr_depth


    ############################
    def transform(self, record):
        """Extract the specified field from the passed DASRecord or dict.
        """
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

        results = []
        for das_record in to_das_record_list(record):
            # If they haven't specified specific fields we should wait for
            # before updates, plan to emit an update after every new record
            # we process. Otherwise, assume we're not going to update unless
            # we see one of the named fields.
            update = bool(not self.update_on_fields)

            timestamp = das_record.timestamp
            if not timestamp:
                logging.info('DASRecord is missing timestamp - skipping')
                continue

            # Get latest values for any of our fields
            fields = das_record.fields
            if self.pressure_field in fields:
                if timestamp >= self.pressure_val_time:
                    self.pressure_val = fields.get(self.pressure_field)
                    self.pressure_val *= self.conv_coefficient

                    # Convert from abs to relative if needed
                    if self.pressure_abs:
                        self.pressure_val -= 10.1325 # dbar

                    self.pressure_val_time = timestamp
                    if self.pressure_field in self.update_on_fields:
                        update = True

            if self.latitude_field in fields:
                if timestamp >= self.latitude_val_time:
                    self.latitude_val = fields.get(self.latitude_field)
                    self.latitude_val_time = timestamp
                    if self.latitude_field in self.update_on_fields:
                        update = True

            # Check if needed all values are present, and none are too old to use
            if self._values_too_old(timestamp):
                continue

            # If we've not seen anything that updates fields that would
            # trigger a new corrected DO value, skip rest of computation.
            if not update:
                logging.debug('No update needed')
                continue

            logging.debug('Computing new depth')
            corr_depth = self.depth_correction(self.pressure_val, self.latitude_val)

            logging.debug('Got correction: depth: %s', corr_depth)

            if corr_depth is None:
                logging.info('Got invalid corrections')
                continue

            # If here, we've got a valid new DO result
            correction_fields = {self.corr_depth_name: corr_depth}

            # Add in metadata if so specified and it's been long enough since
            # we last sent it.
            now = time.time()
            if self.metadata_interval and \
                now - self.metadata_interval > self.last_metadata_send:
                metadata = {'fields': self._metadata()}
                self.last_metadata_send = now
                logging.debug('Emitting metadata: %s', format(metadata))
            else:
                metadata = None


            results.append(DASRecord(timestamp=timestamp,
                                     fields=correction_fields,
                                     metadata=metadata))

        return results


    ############################
    def _values_too_old(self, timestamp):
        """Return true if any values are missing or too old to use."""

        if None in (self.pressure_val, self.latitude_val):
            logging.warning('Not all required values for depth correction are present: '
                          'time: %s, %s: %s, %s: %s',
                          timestamp,
                          self.latitude_field, self.latitude_val,
                          self.pressure_field, self.pressure_val)
            return True

        latitude_max_age = self.max_field_age.get(self.latitude_field, None)
        if (latitude_max_age and timestamp - self.latitude_val_time > latitude_max_age):
            logging.debug('latitude_field too old - max age %g, age %g',
                          latitude_max_age, timestamp - self.latitude_val_time)
            return True

        pressure_max_age = self.max_field_age.get(self.pressure_field, None)
        if (pressure_max_age and timestamp - self.pressure_val_time > pressure_max_age):
            logging.debug('pressure_field too old - max age %g, age %g',
                          pressure_max_age, timestamp - self.pressure_val_time)
            return True

        # Everything is present, and nothing's too old...
        return False
#!/usr/bin/env python3
