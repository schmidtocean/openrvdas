#!/usr/bin/env python3

import sys

from os.path import dirname, realpath
sys.path.append(dirname(dirname(dirname(dirname(realpath(__file__))))))
from logger.utils import formats  # noqa: E402
from logger.utils.das_record import DASRecord  # noqa: E402
from logger.transforms.transform import Transform  # noqa: E402


################################################################################
#
class ParConversionTransform(Transform):
    """Perform the conversion and add the applicable fields to the DASRecord or
    dict.
    """

    def __init__(self,
                 voltage1_field,
                 voltage2_field,
                 irradiance1_name,
                 irradiance2_name,
                 coefficient):

        """
        ```
        voltage1_field,
        voltage2_field
                 Field names from which we should take values for
                 conc, temp, sal, and depth.

        irradiance1_name
        irradiance2_name
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

        if coefficient == 0:
            raise ValueError("coefficient cannot be zero (0)")

        self.coefficient = coefficient
        self.voltage1_field = voltage1_field
        self.voltage2_field = voltage2_field
        self.irradiance1_name = irradiance1_name
        self.irradiance2_name = irradiance2_name

        super().__init__(input_format=formats.Python_Record,
                         output_format=formats.Python_Record)

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

        if isinstance(record, DASRecord):

            if self.voltage1_field in record.fields and isinstance(record.fields[self.voltage1_field], float):
                record.fields[self.irradiance1_name] = self.coefficient * record.fields[self.voltage1_field]

            if self.voltage2_field in record.fields and isinstance(record.fields[self.voltage2_field], float):
                record.fields[self.irradiance2_name] = self.coefficient * record.fields[self.voltage2_field]

            return record

        elif isinstance(record, dict):
            fields = record.get('fields', None)
            if not fields:
                return None

            if self.voltage1_field in fields and isinstance(fields[self.voltage1_field], float):
                fields[self.irradiance1_name] = self.coefficient * fields[self.voltage1_field]

            if self.voltage2_field in fields and isinstance(fields[self.voltage2_field], float):
                fields[self.irradiance2_name] = self.coefficient * fields[self.voltage2_field]

            return record

        return None
