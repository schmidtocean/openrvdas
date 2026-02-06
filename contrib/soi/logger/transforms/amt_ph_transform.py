#!/usr/bin/env python3
"""
AMT pH Sensor Temperature Compensation Transform.
Calculates pH based on AMT Analysenmesstechnik GmbH formulas:
pH = (f(T) * (U - a0) / a1_20C) + 7
f(T) = A0 + A1*T + A2*T^2
"""

import sys
import time
import logging
import yaml

from os.path import dirname, abspath, join, exists, realpath, getmtime

sys.path.append(dirname(dirname(dirname(dirname(realpath(__file__))))))
from logger.utils.das_record import DASRecord, to_das_record_list  # noqa: E402
from logger.transforms.derived_data_transform import DerivedDataTransform  # noqa: E402


################################################################################
#
class AMTPhTransform(DerivedDataTransform):
    """Perform the conversion and add the applicable fields to the DASRecord or
    dict.
    """

    def __init__(
        self,
        output_field,
        voltage_field,
        temp_field,
        a0=None,
        a1_20c=None,
        update_on_fields=[],
        max_field_age={},
        metadata_interval=None,
    ):
        """
        ```
        output_field
                 Name that should be given to transform output values.

        voltage_field
                 Field name for raw pH sensor voltage (U).

        temp_field
                 Field name for seawater temperature (T).

        a0
                 Calibration coefficient a0. If None, will be loaded
                 from YAML file in local/soi/slopes/ directory.

        a1_20c
                 Calibration coefficient a1_20c normalized to 20C.
                 If None, will be loaded from YAML file.

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

        self.output_field = output_field
        self.voltage_field = voltage_field
        self.temp_field = temp_field

        self.a0 = float(a0) if a0 is not None else None
        self.a1_20c = float(a1_20c) if a1_20c is not None else None

        self.update_on_fields = update_on_fields
        self.max_field_age = max_field_age

        self.metadata_interval = metadata_interval
        self.last_metadata_send = 0

        self.voltage_val = None
        self.voltage_val_time = 0
        self.temp_val = None
        self.temp_val_time = 0

        # Calibration file logic
        self.slopes_dir = join(
            dirname(dirname(dirname(dirname(dirname(abspath(__file__)))))),
            "local",
            "soi",
            "slopes",
        )
        self.yaml_loaded = False

    ############################
    def load_calibration_from_yaml(self, field_name):
        """Load calibration coefficients from <field_name>_slope.yaml."""
        yaml_filename = f"{field_name}_slope.yaml"
        yaml_path = join(self.slopes_dir, yaml_filename)

        if exists(yaml_path):
            try:
                age_seconds = time.time() - getmtime(yaml_path)
                if age_seconds > 7 * 24 * 60 * 60:
                    age_days = age_seconds / 86400.0
                    logging.warning(
                        "Calibration file %s is %.1f days old", yaml_path, age_days
                    )
            except Exception as e:
                logging.warning(
                    "Unable to check age of calibration file %s: %s", yaml_path, e
                )
            try:
                with open(yaml_path, "r") as yaml_file:
                    data = yaml.safe_load(yaml_file)
                    if self.a1_20c is None:
                        self.a1_20c = data.get("a1_20c")
                    if self.a0 is None:
                        self.a0 = data.get("a0")

                    if self.a1_20c is not None and self.a0 is not None:
                        logging.info(
                            "Loaded calibration for %s from %s: a1_20c=%s, a0=%s",
                            field_name,
                            yaml_filename,
                            self.a1_20c,
                            self.a0,
                        )
                    else:
                        logging.error(
                            "Missing required a0 and/or a1_20c in %s", yaml_filename
                        )
            except Exception as e:
                logging.error("Error loading YAML from %s: %s", yaml_path, e)
        else:
            logging.warning(
                "Calibration file %s not found for %s", yaml_path, field_name
            )

    ############################
    def fields(self):
        """Which fields are we interested in to produce transformed data?"""
        return [self.voltage_field, self.temp_field]

    ############################
    def _metadata(self):
        """Return a dict of metadata for our derived fields."""

        metadata_fields = {
            self.output_field: {
                "description": "Temperature compensated pH (AMT Deep Sea) from %s"
                % (self.voltage_field),
                "units": "pH",
                "device": "AMTPHTransform",
                "device_type": "DerivedAMTPHTransform",
                "device_type_field": self.output_field,
                "formula": "pH = (f(T)(U-a0)/a1_20C) + 7",
            }
        }
        return metadata_fields

    ############################
    @staticmethod
    def calculate_ph(U, T, a0, a1_20c):
        """
        Calculated temperature-compensated pH values
        """
        # manual equations (3) and (4) from page 5
        A0 = 1.0732
        A1 = -3.9093e-3
        A2 = 1.2333e-5

        # f(T) is the temperature correction factor (Nernst factor)
        f_T = A0 + (A1 * T) + (A2 * (T**2))

        # Calculate pH
        ph = (f_T * (U - a0) / a1_20c) + 7
        ph = round(ph, 3)
        logging.debug("Calculated pH: %s", ph)

        return ph

    ############################
    def transform(self, record):
        """Extract the specified field from the passed DASRecord or dict."""
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

        # Load calibration once if needed
        if not self.yaml_loaded:
            if self.a0 is None or self.a1_20c is None:
                self.load_calibration_from_yaml(self.voltage_field)
            self.yaml_loaded = True

        results = []
        for das_record in to_das_record_list(record):
            # If they haven't specified specific fields we should wait for
            # before updates, plan to emit an update after every new record
            # we process. Otherwise, assume we're not going to update unless
            # we see one of the named fields.
            update = bool(not self.update_on_fields)

            timestamp = das_record.timestamp
            if not timestamp:
                logging.info("DASRecord is missing timestamp - skipping")
                continue

            # Get latest values for any of our fields
            fields = das_record.fields
            if self.voltage_field in fields:
                if timestamp >= self.voltage_val_time:
                    self.voltage_val = fields.get(self.voltage_field)
                    self.voltage_val_time = timestamp
                    if self.voltage_field in self.update_on_fields:
                        update = True

            if self.temp_field in fields:
                if timestamp >= self.temp_val_time:
                    self.temp_val = fields.get(self.temp_field)
                    self.temp_val_time = timestamp
                    if self.temp_field in self.update_on_fields:
                        update = True

            # If we've not seen anything that updates fields that would
            # trigger a new corrected pH value, skip rest of computation.
            if not update:
                logging.debug("No update needed")
                continue

            # Check if needed all values are present, and none are too old to use
            if self._values_too_old(timestamp):
                continue

            # Ensure we have calibration constants
            if self.a0 is None or self.a1_20c is None:
                logging.error(
                    'AMTPhTransform missing calibration coefficients for %s. '
                    'Provide a0 and a1_20c in the same units as %s (counts for SB_ph_analog).',
                    self.voltage_field, self.voltage_field
                )
                raise RuntimeError(
                    f'AMTPhTransform missing calibration coefficients for {self.voltage_field}'
                )

            logging.debug("Computing new pH")
            ph_value = self.calculate_ph(
                self.voltage_val, self.temp_val, self.a0, self.a1_20c
            )

            logging.debug("Got correction: pH: %s", ph_value)

            if ph_value is None:
                logging.info("Got invalid corrections")
                continue

            # If here, we've got a valid new pH result
            correction_fields = {self.output_field: ph_value}

            # Add in metadata if so specified and it's been long enough since
            # we last sent it.
            now = time.time()
            if (
                self.metadata_interval
                and now - self.metadata_interval > self.last_metadata_send
            ):
                metadata = {"fields": self._metadata()}
                self.last_metadata_send = now
                logging.debug("Emitting metadata: %s", format(metadata))
            else:
                metadata = None

            results.append(
                DASRecord(
                    timestamp=timestamp, fields=correction_fields, metadata=metadata
                )
            )

        return results

    ############################
    def _values_too_old(self, timestamp):
        """Return true if any values are missing or too old to use."""

        if self.voltage_val is None or self.temp_val is None:
            logging.warning(
                "Not all required values for pH correction are present: "
                "time: %s, %s: %s, %s: %s",
                timestamp,
                self.voltage_field,
                self.voltage_val,
                self.temp_field,
                self.temp_val,
            )
            return True

        temp_max_age = self.max_field_age.get(self.temp_field, None)
        if temp_max_age and timestamp - self.temp_val_time > temp_max_age:
            logging.warning(
                "temp_field too old - max age %g, age %g",
                temp_max_age,
                timestamp - self.temp_val_time,
            )
            return True

        voltage_max_age = self.max_field_age.get(self.voltage_field, None)
        if voltage_max_age and timestamp - self.voltage_val_time > voltage_max_age:
            logging.warning(
                "voltage_field too old - max age %g, age %g",
                voltage_max_age,
                timestamp - self.voltage_val_time,
            )
            return True

        # Everything is present, and nothing's too old...
        return False
