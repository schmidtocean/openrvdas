#!/bin/bash

OPENVDM_SERVER_URL="http://10.23.9.20"

OPENRVDAS_CONFIG_DEST="/opt/openrvdas/local/soi"
OPENRVDAS_CONFIG_FN="logger_config"
OPENRVDAS_CONFIG_TEMPLATE_FN="logger_config.template"
OPENRVDAS_CONFIG_BACKUP_DEST=${OPENRVDAS_CONFIG_DEST}/backups
HDR_DIR="${OPENRVDAS_CONFIG_DEST}/header-files"

PWD=`pwd`

precheck() {

  if [[ ! -f "${OPENRVDAS_CONFIG_DEST}/${OPENRVDAS_CONFIG_TEMPLATE_FN}" ]]; then
    echo "ERROR: could not find template file... exiting"
    return
  fi

  if [[ ! -d "${OPENRVDAS_CONFIG_DEST}" ]]; then
    echo "ERROR: could not find destination directory... exiting"
    return
  fi

  if [[ ! -d "${OPENRVDAS_CONFIG_BACKUP_DEST}" ]]; then
    echo "ERROR: could not find backup directory... exiting"
    return
  fi

}

query_api() {

  CRUISE_ID=`curl -s "${OPENVDM_SERVER_URL}/api/warehouse/getCruiseID" |
    python3 -c "import sys, json; print(json.load(sys.stdin)['cruiseID'])"`

  echo "Cruise ID: ${CRUISE_ID}"

  CRUISE_START_DATE=`curl -s "${OPENVDM_SERVER_URL}/api/warehouse/getCruiseStartDate" |
    python3 -c "import sys, json; print(json.load(sys.stdin)['cruiseStartDate'].split()[0])" | sed 's?/?-?g'`

  echo "Cruise Start Date: ${CRUISE_START_DATE}"

  CRUISE_END_DATE=`curl -s "${OPENVDM_SERVER_URL}/api/warehouse/getCruiseEndDate" |
    python3 -c "import sys, json; print(json.load(sys.stdin)['cruiseEndDate'].split()[0])" | sed 's?/?-?g'`

  echo "Cruise End Date: ${CRUISE_END_DATE}"

}

build_config_file() {

  sed -e "s/{cruiseID}/$CRUISE_ID/g" \
      -e "s|{cruiseStartDate}|$CRUISE_START_DATE|g" \
      -e "s|{cruiseEndDate}|$CRUISE_END_DATE|g" \
      -e "s|{headerDir}|$HDR_DIR|g" \
      ${OPENRVDAS_CONFIG_DEST}/${OPENRVDAS_CONFIG_TEMPLATE_FN} > ${OPENRVDAS_CONFIG_DEST}/${OPENRVDAS_CONFIG_FN}.yaml

  cd ${OPENRVDAS_CONFIG_DEST}
  tar -czf ${CRUISE_ID}_openrvdas_backup.tar.gz ${OPENRVDAS_CONFIG_FN}.yaml ${OPENRVDAS_CONFIG_TEMPLATE_FN} devices ship_devices.yaml sb_devices.yaml pt_devices.yaml
  if [[ ! -f "${CRUISE_ID}_openrvdas_backup.tar.gz" ]]; then
    echo "ERROR: could not create cruise-specific backup"
    return
  fi

  mv ${CRUISE_ID}_openrvdas_backup.tar.gz ${OPENRVDAS_CONFIG_BACKUP_DEST}

}

main() {

  precheck
  query_api
  build_config_file

  cd $PWD  
}

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------

main "$@"

