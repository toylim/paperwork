#!/bin/sh

# Try to use an AptCacherNg proxy installed close to the gitlab-runner to
# speed up builds

APT_PROXY_CACHE_HOST=192.168.2.120
APT_PROXY_CACHE_PORT=3142

echo "Tags: ${CI_RUNNER_TAGS}"

if echo "${CI_RUNNER_TAGS}" | grep set_apt_proxy > /dev/null ; then
	echo "Proxy ${APT_PROXY_CACHE_HOST}:${APT_PROXY_CACHE_PORT}"
	echo "Acquire::http { Proxy \"http://${APT_PROXY_CACHE}:${APT_PROXY_PORT}\"; }" >> /etc/apt/apt.conf.d/proxy
	echo "APT has been configured to use this proxy"
else
	echo "No tag set_apt_proxy"
fi

apt-get update
