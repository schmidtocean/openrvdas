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
class DensityCorrectionTransform(DerivedDataTransform):
    """Perform the conversion and add the applicable fields to the DASRecord or
    dict.
    """

    def __init__(self,
                 corr_density_name,
                 salinity_field,
                 temperature_field,
                 pressure_field,
                 latitude_field,
                 longitude_field,
                 salinity_coefficient=1,
                 temperature_coefficient=1,
                 pressure_abs=False,
                 pressure_coefficient=1,
                 update_on_fields=[],
                 max_field_age={},
                 metadata_interval=None):

        """
        ```
        salinity_field,
        temperature_field,
        pressure_field,
        latitude_field,
        longitude_field,
                 Field names from which we should take values for
                 salinity, temperature, pressure latitude and longitude.

        corr_density_name
                 Names that should be given to transform output value.

        pressure_abs pressure provided is absolute vs relative sealevel,
                 default: false

        salinity_coefficient,
        temperature_coefficient,
        pressure_coefficient
                 multiply the salinity, temperature or pressure by the co-
                 efficient to convert to appropriate units (PSU, C, dbar)

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

        try:
            if float(salinity_coefficient) == 0 or float(temperature_coefficient) == 0 or float(pressure_coefficient) == 0:
                raise ValueError("conversion coefficients cannot be zero (0)")
        except Exception as err:
            raise ValueError("conversion coefficients must be non-zero (0) numeric values")

        self.salinity_field = salinity_field
        self.temperature_field = temperature_field
        self.pressure_field = pressure_field
        self.latitude_field = latitude_field
        self.longitude_field = longitude_field
        
        self.salinity_coefficient = salinity_coefficient
        self.temperature_coefficient = temperature_coefficient
        self.pressure_coefficient = pressure_coefficient

        self.pressure_abs = pressure_abs

        self.corr_density_name = corr_density_name

        self.update_on_fields = update_on_fields
        self.max_field_age = max_field_age
        self.field_age = {}

        self.metadata_interval = metadata_interval
        self.last_metadata_send = 0

        self.salinity_val = None
        self.salinity_val_time = 0
        self.temperature_val = None
        self.temperature_val_time = 0
        self.pressure_val = None
        self.pressure_val_time = 0
        self.latitude_val = None
        self.latitude_val_time = 0
        self.longitude_val = None
        self.longitude_val_time = 0

    ############################
    def fields(self):
        """Which fields are we interested in to produce transformed data?"""
        return [self.salinity_field, self.temperature_field, self.pressure_field, self.latitude_field, self.longitude_field]

    ############################
    def _metadata(self):
        """Return a dict of metadata for our derived fields."""

        metadata_fields = {
            self.corr_density_name: {
                'description': 'Derived density correction from %s, %s, %s, %s, %s'
                % (self.salinity_field, self.temperature_field, self.pressure_field,
                self.latitude_field, self.longitude_field),
                'units': 'kg/m^3',
                'device': 'DensityCorrectionTransform',
                'device_type': 'DerivedDensityCorrectionTransform',
                'device_type_field': self.corr_density_name
            }
        }
        return metadata_fields

    ############################
    @staticmethod
    def density_correction(salinity, temperature, pressure, latitude, longitude):

        """
        calculated corrected density values
        """
        absolute_salinity = gsw.SA_from_SP(salinity, pressure, longitude, latitude)
        # logging.debug("SA: %s", absolute_salinity)

        corr_density = gsw.density.rho_t_exact(absolute_salinity, temperature, pressure)
        # logging.debug("Corr Density: %s", corr_density)

        corr_density = round(corr_density, 2)

        return corr_density


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
            
            if self.salinity_field in fields:
                if timestamp >= self.salinity_val_time:
                    self.salinity_val = fields.get(self.salinity_field)
                    self.salinity_val *= self.salinity_coefficient
                    self.salinity_val_time = timestamp
                    if self.salinity_field in self.update_on_fields:
                        update = True

            if self.temperature_field in fields:
                if timestamp >= self.temperature_val_time:
                    self.temperature_val = fields.get(self.temperature_field)
                    self.temperature_val *= self.temperature_coefficient
                    self.temperature_val_time = timestamp
                    if self.pressure_field in self.update_on_fields:
                        update = True

            if self.pressure_field in fields:
                if timestamp >= self.pressure_val_time:
                    self.pressure_val = fields.get(self.pressure_field)
                    self.pressure_val *= self.pressure_coefficient

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

            if self.longitude_field in fields:
                if timestamp >= self.longitude_val_time:
                    self.longitude_val = fields.get(self.longitude_field)
                    self.longitude_val_time = timestamp
                    if self.longitude_field in self.update_on_fields:
                        update = True

            # Check if needed all values are present, and none are too old to use
            if self._values_too_old(timestamp):
                continue

            # If we've not seen anything that updates fields that would
            # trigger a new corrected DO value, skip rest of computation.
            if not update:
                logging.debug('No update needed')
                continue

            logging.debug('Computing new density')
            corr_density = self.density_correction(self.salinity_val,
                                                   self.temperature_val,
                                                   self.pressure_val,
                                                   self.latitude_val,
                                                   self.longitude_val)

            if corr_density is None:
                logging.info('Got invalid corrections')
                continue

            logging.debug("Density: %s", corr_density)

            # If here, we've got a valid new DO result
            correction_fields = {self.corr_density_name: corr_density}

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

            results.append(DASRecord(timestamp=timestamp, fields=correction_fields,
                                     metadata=metadata))

        return results


    ############################
    def _values_too_old(self, timestamp):
        """Return true if any values are missing or too old to use."""

        if None in (self.salinity_val, self.temperature_val, self.pressure_val):
            logging.warning('Not all required values for density correction are present: '
                          'time: %s, %s: %s, %s: %s, %s: %s, %s: %s, %s: %s',
                          timestamp,
                          self.salinity_field, self.salinity_val,
                          self.temperature_field, self.temperature_val,
                          self.pressure_field, self.pressure_val,
                          self.latitude_field, self.latitude_val,
                          self.longitude_field, self.longitude_val)
            return True

        salinity_max_age = self.max_field_age.get(self.salinity_field, None)
        if (salinity_max_age and timestamp - self.salinity_val_time > salinity_max_age):
            logging.debug('salinity_field too old - max age %g, age %g',
                          salinity_max_age, timestamp - self.salinity_val_time)
            return True

        temperature_max_age = self.max_field_age.get(self.temperature_field, None)
        if (temperature_max_age and timestamp - self.temperature_val_time > temperature_max_age):
            logging.debug('temperature_field too old - max age %g, age %g',
                          temperature_max_age, timestamp - self.temperature_val_time)
            return True

        pressure_max_age = self.max_field_age.get(self.pressure_field, None)
        if (pressure_max_age and timestamp - self.pressure_val_time > pressure_max_age):
            logging.debug('pressure_field too old - max age %g, age %g',
                          pressure_max_age, timestamp - self.pressure_val_time)
            return True

        latitude_max_age = self.max_field_age.get(self.latitude_field, None)
        if (latitude_max_age and timestamp - self.latitude_val_time > latitude_max_age):
            logging.debug('latitude_field too old - max age %g, age %g',
                          latitude_max_age, timestamp - self.latitude_val_time)
            return True

        longitude_max_age = self.max_field_age.get(self.longitude_field, None)
        if (longitude_max_age and timestamp - self.longitude_val_time > longitude_max_age):
            logging.debug('longitude_field too old - max age %g, age %g',
                          longitude_max_age, timestamp - self.longitude_val_time)
            return True

        # Everything is present, and nothing's too old...
        return False
