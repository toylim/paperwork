#!/bin/sh

# Try to use an AptCacherNg proxy installed close to the gitlab-runner to
# speed up builds

APT_PROXY_CACHE_HOST=192.168.2.120
APT_PROXY_CACHE_PORT=3142

apt-get update
apt-get install -y -qq netcat-openbsd

echo "Proxy ${APT_PROXY_CACHE_HOST}:${APT_PROXY_CACHE_PORT}"
if ! nc -w 5 -z ${APT_PROXY_CACHE_HOST} ${APT_PROXY_CACHE_PORT} ; then
	echo "Proxy appears to be unreachable"
	exit 0
fi

echo "Acquire::http { Proxy \"http://${APT_PROXY_CACHE}:${APT_PROXY_PORT}\"; }" >> /etc/apt/apt.conf.d/proxy
echo "APT has been configured to use this proxy"

apt-get update
