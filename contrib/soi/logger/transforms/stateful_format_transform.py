#!/usr/bin/env python3

import logging
import time

from logger.transforms.transform import Transform
from logger.utils.das_record import to_das_record_list

################################################################################


class StatefulFormatTransform(Transform):
    """
    Caches the latest value of every field it sees.
    Attempts to emit a formatted string using the latest cached values.
    """

    def __init__(self, format_str, max_age_seconds=None):
        """
        format_str:      Python format string (e.g. "{Lat},{Lon},{Oxygen}")
        max_age_seconds: If a stored value is older than this, it is discarded
                         and the format will fail/skip until refreshed.
        """
        # Call the parent class's constructor first
        super().__init__()
        self.format_str = format_str
        self.max_age_seconds = max_age_seconds

        # The Memory: Dictionary to store { 'FieldName': Value }
        self.state = {}
        # The Clock: Dictionary to store { 'FieldName': Timestamp }
        self.state_ts = {}

    def transform(self, record):
        if not record:
            return None

        results = []

        # Handle list of records
        das_records = to_das_record_list(record)

        for rec in das_records:
            if not rec.fields:
                continue

            # 1. Update Memory with new data
            timestamp = rec.timestamp or time.time()
            for key, val in rec.fields.items():
                self.state[key] = val
                self.state_ts[key] = timestamp

            # 2. Prune old data (if max_age set)
            if self.max_age_seconds:
                current_time = time.time()
                # Find keys to delete
                expired_keys = [
                    k
                    for k, ts in self.state_ts.items()
                    if (current_time - ts) > self.max_age_seconds
                ]
                for k in expired_keys:
                    logging.debug(f"Field {k} expired (Age > {self.max_age_seconds}s)")
                    del self.state[k]
                    del self.state_ts[k]

            # 3. Try to Format
            try:
                # Magic: Uses self.state dictionary to fill in the blanks
                formatted_string = self.format_str.format(**self.state)
                results.append(formatted_string)
            except KeyError as e:
                # This is normal. It means we haven't seen the field 'e' yet,
                # or it expired. We just wait for the next record.
                logging.debug(f"Missing field for format: {e}")
                continue
            except Exception as e:
                logging.error(f"Error formatting string: {e}")

        return results if results else None
