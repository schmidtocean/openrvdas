import sys
from os.path import dirname, realpath

sys.path.append(dirname(dirname(dirname(dirname(realpath(__file__))))))
from logger.utils import formats  # noqa: E402
from logger.utils.das_record import DASRecord  # noqa: E402
from logger.transforms.transform import Transform  # noqa: E402

################################################################################
#
class SlopeInterceptTransform(Transform):
    """Apply a slope-intercept correction (mx + b) to a specified field in the DASRecord or dict."""

    def __init__(self, input_field, output_field, m=1, b=0):
        """
        input_field
                 Field name for the input value.

        output_field
                 Field name for the corrected output value.

        m
                 Slope multiplier.

        b
                 Offset to be added to the slope correction.
        """
        self.m = m
        self.b = b
        self.input_field = input_field
        self.output_field = output_field

        super().__init__(input_format=formats.Python_Record,
                         output_format=formats.Python_Record)

    def transform(self, record):
        """Apply the slope-intercept formula (mx + b) to the specified field in the record."""
        if not record:
            return None

        if isinstance(record, list):
            return [self.transform(single_record) for single_record in record]

        if isinstance(record, DASRecord):
            if self.input_field in record.fields and isinstance(record.fields[self.input_field], float):
                record.fields[self.output_field] = self.m * record.fields[self.input_field] + self.b
            return record

        elif isinstance(record, dict):
            fields = record.get('fields', None)
            if fields and self.input_field in fields and isinstance(fields[self.input_field], float):
                fields[self.output_field] = self.m * fields[self.input_field] + self.b
            return record

        return None
