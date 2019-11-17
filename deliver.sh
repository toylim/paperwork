#!/bin/sh

binary="$1"
os="$2"
exe_suffix="$3"

if [ "${os}" = "linux" ] ; then
  arch="amd64"
else
  arch="x86"
fi

if [ "${os}" = "linux" ] ; then
  arch="amd64"
else
  arch="x86"
fi

if [ -z "$RCLONE_CONFIG_OVHSWIFT_USER" ] ; then
  echo "Delivery: No rclone credentials provided."
  exit 0
fi

if ! which rclone; then
  echo "rclone not available."
  exit 1
fi

echo "Delivering: ${binary} (${CI_COMMIT_REF_NAME} - ${CI_COMMIT_SHORT_SHA})"
echo "Destination: ${os}/${arch} (${exe_suffix})"

out_name="paperwork-${CI_COMMIT_REF_NAME}-${CI_COMMIT_SHORT_SHA}${exe_suffix}"
latest_name="paperwork-${CI_COMMIT_REF_NAME}-latest${exe_suffix}"


echo "rclone: ${out_name}"

if ! rclone --config ./rclone.conf copyto "${binary}" "ovhswift:download_openpaperwork/${os}/${arch}/${out_name}" ; then
  echo "rclone failed"
  exit 1
fi

echo "rclone: ${latest_name}"

if ! rclone --config ./rclone.conf copyto "ovhswift:download_openpaperwork/${os}/${arch}/${out_name}" "ovhswift:download_openpaperwork/${DELIVERY_PATH}/${os}/${arch}/${latest_name}" ; then
  echo "rclone failed"
  exit 1
fi

echo Success
exit 0
