#!/bin/sh

input_file="$1"
destination="$2"

if ! [ -f "${input_file}" ] || [ -z "${destination}" ] ; then
  echo "You must specify an input file to upload and a destination directory"
  exit 1
fi

if [ -z "$RCLONE_CONFIG_OVHSWIFT_USER" ] ; then
  echo "Delivery: No rclone credentials provided."
  exit 0
fi

if ! which rclone; then
  echo "rclone not available."
  exit 1
fi

echo "Delivering: ${input_file} (${CI_COMMIT_REF_NAME} - ${CI_COMMIT_SHORT_SHA})"

out_name="${CI_COMMIT_REF_NAME}_$(date "+%Y%m%d_%H%M%S")_${CI_COMMIT_SHORT_SHA}"
latest_name="${CI_COMMIT_REF_NAME}-latest"

if ! rclone --config ./ci/rclone.conf copy \
    "${input_file}" \
    "ovhswift:download_openpaperwork/data/paperwork/${out_name}/${destination}/" ; then
  echo "rclone failed"
  exit 1
fi

if ! rclone --config ./ci/rclone.conf sync \
    "${input_file}" \
    "ovhswift:download_openpaperwork/data/paperwork/${latest_name}/${destination}/" ; then
  echo "rclone failed"
  exit 1
fi

echo Success
exit 0
