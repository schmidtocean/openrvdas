# OpenRVDAS Configuration and Customization

### Scripts:
**build_logger_config.sh** -> This file builds an OpenRVDAS configuration file from a template file (`logger_config.template`) and the OpenVDM API.  This file lives in the rvdas user's home directory on the OpenRVDAS VM

### Configuration Files:
**local/soi/rov_devices.yaml** -> This file contains the mappings between the device-type configurations and the actual devices installed on the vehicle.

**local/soi/ship_devices.yaml** -> This file contains the mappings between the device-type configurations and the actual devices installed on the ship.

**local/soi/devices/*.yaml** -> This directory contains the OpenRVDAS device-type configurations for FKT and SuBastian.

**logger_config.template** -> This is the template file used to build an OpenRVDAS configuration file.  Changes to the OpenRVDAS logger configurations should be made first to this file and then use the `build_logger_config.sh` script to build the actual OpenRVDAS logger configuration. This file lives in the rvdas user's home directory on the OpenRVDAS VM

**rov_devices.yaml** -> This file contains the mappings between the device-type configurations and the actual devices installed on the vehicle. This file lives at `/opt/openrvdas/local/soi` on the OpenRVDAS VM

**ship_devices.yaml** -> This file contains the mappings between the device-type configurations and the actual devices installed on the ship. This file lives at `/opt/openrvdas/local/soi` on the OpenRVDAS VM

### Customizations
**contrib/\soi/\readers** -> Contains custom readers used in the SOI implementation of OpenRVDAS

**contrib/\soi/\transforms** -> Contains custom transforms used in the SOI implementation of OpenRVDAS

**contrib/\soi/\writers** -> Contains custom writers used in the SOI implementation of OpenRVDAS

### Install:
Add a symbolic link from the `local/soi` directory to `/opt/openrvdas/local` directory. Files must be readable by the rvdas user.
Add a symbolic link from the `contrib/soi` directory to `/opt/openrvdas/contrib` directory. Files must be readable by the rvdas user.
