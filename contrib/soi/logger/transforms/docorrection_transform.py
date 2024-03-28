#!/usr/bin/env python3

import sys
import math
import time
import logging

from os.path import dirname, realpath
sys.path.append(dirname(dirname(dirname(dirname(realpath(__file__))))))
from logger.utils.das_record import DASRecord, to_das_record_list  # noqa: E402
from logger.transforms.derived_data_transform import DerivedDataTransform  # noqa: E402

# Salinity and solublity constants
B0 = -6.24097E-03
B1 = -6.93498E-03
B2 = -6.90358E-03
B3 = -4.29155E-03
C0 = -3.11680E-07

# Atmospheric pressure
PATM = 1013.25


################################################################################
#
class DOCorrectionTransform(DerivedDataTransform):
    """Perform the conversion and add the applicable fields to the DASRecord or
    dict.
    """

    def __init__(self,
                 conc_field,
                 temp_field,
                 sal_field,
                 corr_conc_name,
                 corr_sat_name,
                 depth_field=None,
                 pressure_field=None,
                 conv_coefficient=1,
                 sal_setting=0,
                 update_on_fields=[],
                 max_field_age={},
                 metadata_interval=None):

        """
        ```
        conc_field,
        temp_field,
        sal_field,
        depth_field,
        pressure_field,
                 Field names from which we should take values for
                 conc, temp, sal, and depth.

        conv_coefficient
                 conversion coefficient to convert pressure to dBar

        corr_conc_name
        corr_sat_name
                 Names that should be given to transform output values.

        sal_setting
                 Sensor setting, unsure where this is pulled from but the
                 documentation says the default value should be 0

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

        if depth_field is None and pressure_field is None:
            raise ValueError("Must declare a pressure_field OR depth_field")

        if conv_coefficient == 0:
            raise ValueError("conv_coefficient cannot be zero (0)")

        self.conc_field = conc_field
        self.temp_field = temp_field
        self.sal_field = sal_field
        self.sal_setting = sal_setting
        self.depth_field = depth_field if depth_field is not None else pressure_field
        self.use_pressure = False if depth_field is not None else True

        self.conv_coefficient = conv_coefficient

        self.corr_conc_name = corr_conc_name
        self.corr_sat_name = corr_sat_name

        self.update_on_fields = update_on_fields
        self.max_field_age = max_field_age
        self.field_age = {}

        self.metadata_interval = metadata_interval
        self.last_metadata_send = 0

        self.conc_val = None
        self.temp_val = None
        self.sal_val = None
        self.depth_val = None

        self.conc_val_time = 0
        self.temp_val_time = 0
        self.sal_val_time = 0
        self.depth_val_time = 0

    ############################
    def fields(self):
        """Which fields are we interested in to produce transformed data?"""
        return [self.conc_field, self.temp_field, self.sal_field,
                self.sal_setting, self.depth_field]

    ############################
    def _metadata(self):
        """Return a dict of metadata for our derived fields."""

        metadata_fields = {
            self.corr_conc_name: {
                'description': 'Derived DO concentration from %s, %s, %s, %s, %s'
                % (self.conc_field, self.temp_field, self.sal_field,
                   self.depth_field, self.sal_setting),
                'units': '\u03BCmol/l',
                'device': 'DOCorrectionTransform',
                'device_type': 'DerivedDOCorrectionTransform',
                'device_type_field': self.corr_conc_name
            },
            self.corr_sat_name: {
                'description': 'Derived DO saturation from %s, %s, %s, %s, %s'
                % (self.conc_field, self.temp_field, self.sal_field,
                   self.depth_field, self.sal_setting),
                'units': '%',
                'device': 'DOCorrectionTransform',
                'device_type': 'DerivedDOCorrectionTransform',
                'device_type_field': self.corr_sat_name
            }
        }
        return metadata_fields

    ############################
    @staticmethod
    def do_correction(conc=None,
                      temp=None,
                      sal=None,
                      depth=None,
                      sal_setting=0,
                      conv_coefficient = 1,
                      use_pressure = True
                      ):

        """
        calculated corrected concentration/saturation values
        """

        # Scaled temp
        scaled_temp = math.log((298.15 - temp) /(273.15 + temp))

        # Pressure compensation factor
        comp_pressure_factor = abs(depth)/1000 * 0.032+1

        #Salinity compensation factor
        comp_sal_factor = math.exp((sal-sal_setting) * (B0 + B1 * scaled_temp + B2 * scaled_temp**2 + B3 * scaled_temp**3) +  C0 * (sal**2 - sal_setting**2))

        logging.debug('Scaled temp: %0.2f', scaled_temp)
        logging.debug('Salinity constant: %0.2f', comp_sal_factor)

        # Salinity and Pressure compensated DO in micromolar
        corr_conc = conc * comp_sal_factor * comp_pressure_factor
        corr_conc = round(corr_conc, 2)
        logging.debug('DO concentration in micromolar, sal and pressure compensated: %0.2f', corr_conc)

        # DO Solubility product constant
        comp_pressure_factor = (PATM / 1013.25) * 44.659 * math.exp((2.00856+3.224*(math.log((298.15-temp)/(273.15+temp)))+3.99063*(math.log((298.15-temp)/(273.15+temp)))**2+4.80299*(math.log((298.15-temp)/(273.15+temp)))**3+0.978188*(math.log((298.15-temp)/(273.15+temp)))**4+1.71069*(math.log((298.15-temp)/(273.15+temp)))**5)+(sal*(-0.00624097-0.00693498*(math.log((298.15-temp)/(273.15+temp)))+-0.00690358*(math.log((298.15-temp)/(273.15+temp)))**2+-0.00429155*(math.log((298.15-temp)/(273.15+temp)))**3))+(-0.00000031168*sal**2))

        # Compensated O2 airsat
        corr_sat = 100 * corr_conc / comp_pressure_factor
        corr_sat = round(corr_sat, 2)
        logging.debug('DO airsaturation, sal and pressure compensated: %0.2f', corr_sat)

        return (corr_conc, corr_sat)


    ############################
    def transform(self, record):
        """Extract the specified field from the passed DASRecord or dict.
        """
        if not record:
            return None

        # If we've got a list, hope it's a list of records. Recurse,
        # calling transform() on each of the list elements in order and
        # return the resulting list.
        if isinstance(record, list):
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
            if self.conc_field in fields:
                if timestamp >= self.conc_val_time:
                    self.conc_val = fields.get(self.conc_field)
                    # self.conc_val *= self.convert_conc_factor
                    self.conc_val_time = timestamp
                    if self.conc_field in self.update_on_fields:
                        update = True

            if self.temp_field in fields:
                if timestamp >= self.temp_val_time:
                    self.temp_val = fields.get(self.temp_field)
                    # self.temp_val *= self.convert_temp_factor
                    self.temp_val_time = timestamp
                    if self.temp_field in self.update_on_fields:
                        update = True

            if self.sal_field in fields:
                if timestamp >= self.sal_val_time:
                    self.sal_val = fields.get(self.sal_field)
                    # self.sal_val *= self.convert_sal_factor
                    self.sal_val_time = timestamp
                    if self.sal_field in self.update_on_fields:
                        update = True

            if self.depth_field in fields:
                if timestamp >= self.depth_val_time:
                    self.depth_val = fields.get(self.depth_field)
                    # self.depth_val *= self.convert_depth_factor
                    self.depth_val_time = timestamp
                    if self.depth_field in self.update_on_fields:
                        update = True

            # Check if needed all values are present, and none are too old to use
            if self._values_too_old(timestamp):
                continue

            # If we've not seen anything that updates fields that would
            # trigger a new corrected DO value, skip rest of computation.
            if not update:
                logging.debug('No update needed')
                continue

            logging.debug('Computing new DO')
            (corr_conc, corr_sat) = self.do_correction(conc=self.conc_val,
                                                       temp=self.temp_val,
                                                       sal=self.sal_val,
                                                       depth=self.depth_val,
                                                       sal_setting=self.sal_setting,
                                                       use_pressure = self.use_pressure,
                                                       conv_coefficient = self.conv_coefficient
                                                       )

            logging.debug('Got corrections: conc: %s, sat: %s', corr_conc, corr_sat)

            if None in (corr_conc, corr_sat):
                logging.info('Got invalid corrections')
                continue

            # If here, we've got a valid new DO result
            correction_fields = {self.corr_conc_name: corr_conc,
                                self.corr_sat_name: corr_sat}

            # Add in metadata if so specified and it's been long enough since
            # we last sent it.
            now = time.time()
            if self.metadata_interval and \
               now - self.metadata_interval > self.last_metadata_send:
                metadata = {'fields': self._metadata()}
                self.last_metadata_send = now
                logging.debug('Emitting metadata: %s', metadata)
            else:
                metadata = None

            results.append(DASRecord(timestamp=timestamp, fields=correction_fields,
                                     metadata=metadata))

        return results


    ############################
    def _values_too_old(self, timestamp):
        """Return true if any values are missing or too old to use."""

        if None in (self.conc_val, self.temp_val, self.sal_val, self.depth_val):
            logging.debug('Not all required values for DO correction are present: '
                          'time: %s, %s: %s, %s: %s, %s: %s, %s: %s',
                          timestamp,
                          self.conc_field, self.conc_val,
                          self.temp_field, self.temp_val,
                          self.sal_field, self.sal_val,
                          self.depth_field, self.depth_val)
            return True

        conc_max_age = self.max_field_age.get(self.conc_field, None)
        if (conc_max_age and timestamp - self.conc_val_time > conc_max_age):
            logging.debug('conc_field too old - max age %g, age %g',
                          conc_max_age, timestamp - self.conc_val_time)
            return True

        temp_max_age = self.max_field_age.get(self.temp_field, None)
        if temp_max_age:
            if timestamp - self.temp_val_time > temp_max_age:
                logging.debug('temp_field too old - max age %g, age %g',
                              temp_max_age, timestamp - self.temp_val_time)
                return True

        sal_max_age = self.max_field_age.get(self.sal_field, None)
        if sal_max_age:
            if timestamp - self.sal_val_time > sal_max_age:
                logging.debug('sal_field too old - max age %g, age %g',
                              sal_max_age, timestamp - self.sal_val_time)
                return True

        depth_max_age = self.max_field_age.get(self.depth_field, None)
        if depth_max_age:
            if timestamp - self.depth_val_time > depth_max_age:
                logging.debug('%s too old - max age %g, age %g',
                              'pressure_field' if self.use_pressure else 'depth_field', depth_max_age, timestamp - self.depth_val_time)
                return True

        # Everything is present, and nothing's too old...
        return False
