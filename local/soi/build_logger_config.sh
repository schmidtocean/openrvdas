#!/bin/bash

OPENVDM_SERVER_URL="http://10.128.0.26"

OPENRVDAS_CONFIG_DEST="/opt/openrvdas/local/soi"
OPENRVDAS_CONFIG_FN="logger_config"
OPENRVDAS_CONFIG_TEMPLATE_FN="logger_config.template"
OPENRVDAS_CONFIG_BACKUP_DEST=${OPENRVDAS_CONFIG_DEST}/backups
OPENRVDAS_DATA_DEST="/mnt/sio_data1/openrvdas"
HDR_DIR="${OPENRVDAS_CONFIG_DEST}/header-files"

if [ ${1:-prod} == 'devel' ]; then
  OPENVDM_SERVER_URL="http://10.128.0.48"
  OPENRVDAS_CONFIG_BACKUP_DEST=${OPENRVDAS_CONFIG_DEST}/backups_devel
  OPENRVDAS_DATA_DEST="/data/openrvdas"
fi

PWD=`pwd`

#########################################################################
#########################################################################
# Return a normalized yes/no for a value
yes_no() {
    QUESTION=$1
    DEFAULT_ANSWER=$2

    while true; do
        read -p "$QUESTION ($DEFAULT_ANSWER) " yn
        case $yn in
            [Yy]* )
                YES_NO_RESULT=yes
                break;;
            [Nn]* )
                YES_NO_RESULT=no
                break;;
            "" )
                YES_NO_RESULT=$DEFAULT_ANSWER
                break;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

precheck() {

  if [[ ! -f "${OPENRVDAS_CONFIG_DEST}/${OPENRVDAS_CONFIG_TEMPLATE_FN}" ]]; then
    echo "ERROR: could not find template file... exiting"
    exit 1
  fi

  if [[ ! -d "${OPENRVDAS_CONFIG_DEST}" ]]; then
    echo "ERROR: could not find destination directory... exiting"
    exit 1
  fi

  if [[ ! -d "${OPENRVDAS_CONFIG_BACKUP_DEST}" ]]; then
    yes_no "Could not find logger config backup directory ${OPENRVDAS_CONFIG_BACKUP_DEST}... create it? " "yes"
    if [ $YES_NO_RESULT == "yes" ]; then
      mkdir -p ${OPENRVDAS_CONFIG_BACKUP_DEST}
    fi
  fi
  
  if [[ ! -d "${OPENRVDAS_CONFIG_BACKUP_DEST}" ]]; then
    echo "ERROR: could not find backup directory... exiting"
    exit 1
  fi

}

query_api() {

  CRUISE_ID_RAW=`curl --connect-timeout 5 -s "${OPENVDM_SERVER_URL}/api/warehouse/getCruiseID" || echo "Unable to communicate with OpenVDM API. Exiting...";exit 1`
  CRUISE_ID=`echo $CRUISE_ID_RAW | python3 -c "import sys, json; print(json.load(sys.stdin)['cruiseID'])"`

  echo "Cruise ID: ${CRUISE_ID}"

  CRUISE_START_DATE_RAW=`curl --connect-timeout 5 -s "${OPENVDM_SERVER_URL}/api/warehouse/getCruiseStartDate" || echo "Unable to communicate with OpenVDM API. Exiting...";exit 1`
  CRUISE_START_DATE=`echo $CRUISE_START_DATE_RAW | python3 -c "import sys, json; print(json.load(sys.stdin)['cruiseStartDate'].split()[0])" | sed 's?/?-?g'`

  echo "Cruise Start Date: ${CRUISE_START_DATE}"

  CRUISE_END_DATE_RAW=`curl --connect-timeout 5 -s "${OPENVDM_SERVER_URL}/api/warehouse/getCruiseEndDate" || echo "Unable to communicate with OpenVDM API. Exiting...";exit 1`
  CRUISE_END_DATE=`echo $CRUISE_END_DATE_RAW | python3 -c "import sys, json; print(json.load(sys.stdin)['cruiseEndDate'].split()[0])" | sed 's?/?-?g'`

  echo "Cruise End Date: ${CRUISE_END_DATE}"

}

build_config_file() {

  sed -e "s/{cruiseID}/$CRUISE_ID/g" \
      -e "s|{cruiseStartDate}|$CRUISE_START_DATE|g" \
      -e "s|{cruiseEndDate}|$CRUISE_END_DATE|g" \
      -e "s|{headerDir}|$HDR_DIR|g" \
      -e "s|{dataDir}|$OPENRVDAS_DATA_DEST|g"\
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

