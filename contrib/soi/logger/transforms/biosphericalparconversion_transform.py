#!/usr/bin/env python3

import sys

from os.path import dirname, realpath
sys.path.append(dirname(dirname(dirname(dirname(dirname(realpath(__file__)))))))
from logger.utils import formats  # noqa: E402
from logger.utils.das_record import DASRecord  # noqa: E402
from logger.transforms.transform import Transform  # noqa: E402


################################################################################
#
class BiosphericalParConversionTransform(Transform):
    """Perform the conversion and add the applicable fields to the DASRecord or
    dict.
    """

    def __init__(self,
                 voltage_field,
                 irradiance_name,
                 coefficient=1,
                 offset=0):

        """
        ```
        voltage_field
                 Field name from which we should take values for
                 conc, temp, sal, and depth.

        irradiance_name
                 Names that should be given to transform output values.

        coefficient
                 What to multiple the raw voltage by to get the irradiance

        offset
                 What to add to the raw voltage x coefficient to correct the
                 irradiance value
        ```
        """

        if coefficient == 0:
            raise ValueError("coefficient cannot be zero (0)")

        self.coefficient = coefficient
        self.offset = offset
        self.voltage_field = voltage_field
        self.irradiance_name = irradiance_name

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

            if self.voltage_field in record.fields and isinstance(record.fields[self.voltage_field], float):
                record.fields[self.irradiance_name] = self.coefficient * record.fields[self.voltage_field] + self.offset

            return record

        elif isinstance(record, dict):
            fields = record.get('fields', None)
            if not fields:
                return None

            if self.voltage_field in fields and isinstance(fields[self.voltage_field], float):
                fields[self.irradiance_name] = self.coefficient * fields[self.voltage_field] + self.offset

            return record

        return None
