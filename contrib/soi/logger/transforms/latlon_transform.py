#!/usr/bin/env python3
"""
A transform that converts unsigned lat/lon and hemisphere fields into
single signed latitude/longitude fields.

This is a stateful transform that remembers field values as they
arrive in different records.
"""
import logging
import time

from logger.utils.das_record import DASRecord, to_das_record_list
from logger.transforms.derived_data_transform import DerivedDataTransform

class LatLonTransform(DerivedDataTransform):
    def __init__(self, raw_lat_field, raw_lat_hemi_field,
                 raw_lon_field, raw_lon_hemi_field,
                 derived_lat_field, derived_lon_field,
                 update_on_fields=None, max_field_age=None):
        """
        Initialize the transform.
        Args:
          raw_lat_field:       Name of the raw latitude field to read
          raw_lat_hemi_field:  Name of the raw latitude hemisphere field
          raw_lon_field:       Name of the raw longitude field to read
          raw_lon_hemi_field:  Name of the raw longitude hemisphere field
          derived_lat_field:   Name of the new signed latitude field to write
          derived_lon_field:   Name of the new signed longitude field to write
          update_on_fields:    List of fields that trigger an output. If None,
                               any field update triggers an output.
          max_field_age:       Dict of {field_name: seconds} for data staleness.
        """
        self.raw_lat_field = raw_lat_field
        self.raw_lat_hemi_field = raw_lat_hemi_field
        self.raw_lon_field = raw_lon_field
        self.raw_lon_hemi_field = raw_lon_hemi_field
        self.derived_lat_field = derived_lat_field
        self.derived_lon_field = derived_lon_field
        
        self.update_on_fields = update_on_fields or []
        self.max_field_age = max_field_age or {}

        self.state = {
            self.raw_lat_field: None,
            self.raw_lat_hemi_field: None,
            self.raw_lon_field: None,
            self.raw_lon_hemi_field: None,
        }
        self.state_timestamps = {
            self.raw_lat_field: 0,
            self.raw_lat_hemi_field: 0,
            self.raw_lon_field: 0,
            self.raw_lon_hemi_field: 0,
        }

    ############################
    def fields(self):
        """Which fields are we interested in?"""
        return [self.raw_lat_field, self.raw_lat_hemi_field,
                self.raw_lon_field, self.raw_lon_hemi_field]

    ############################
    def transform(self, record):
        """Update state and compute derived values if possible."""
        if not record:
            return None

        if isinstance(record, list):
            results = []
            for single_record in record:
                results.append(self.transform(single_record))
            return [r for r in results if r] # Filter out Nones

        results = []
        for das_record in to_das_record_list(record):
            timestamp = das_record.timestamp
            if not timestamp:
                logging.debug('DASRecord is missing timestamp - skipping')
                continue

            update_triggered = not self.update_on_fields
            fields_in_record = das_record.fields
            
            for field_name in self.fields():
                if field_name in fields_in_record:
                    if timestamp >= self.state_timestamps[field_name]:
                        self.state[field_name] = fields_in_record[field_name]
                        self.state_timestamps[field_name] = timestamp
                        if field_name in self.update_on_fields:
                            update_triggered = True

            if not update_triggered:
                continue

            if self._values_missing_or_stale(timestamp):
                continue

            new_record_fields = {}
            try:
                lat_val = float(self.state[self.raw_lat_field])
                if self.state[self.raw_lat_hemi_field] == 'S':
                    lat_val = -lat_val
                new_record_fields[self.derived_lat_field] = lat_val

                lon_val = float(self.state[self.raw_lon_field])
                if self.state[self.raw_lon_hemi_field] == 'W':
                    lon_val = -lon_val
                new_record_fields[self.derived_lon_field] = lon_val
                
                results.append(DASRecord(timestamp=timestamp,
                                         fields=new_record_fields))

            except (ValueError, TypeError) as e:
                logging.warning(f"Error converting lat/lon state: {e}. State: {self.state}")

        return results if results else None

    ############################
    def _values_missing_or_stale(self, timestamp):
        """Return true if any values are missing or too old to use."""
        for field_name in self.fields():
            # Check if missing
            if self.state[field_name] is None:
                logging.debug(f"Waiting for value: {field_name}")
                return True # Value is missing

            # Check if stale
            max_age = self.max_field_age.get(field_name)
            if max_age:
                age = timestamp - self.state_timestamps[field_name]
                if age > max_age:
                    logging.warning(f"{field_name} value is stale (age {age}s > max {max_age}s)")
                    return True # Value is stale
        
        # Everything is present and not stale
        return False