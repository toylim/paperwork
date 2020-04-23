#!/bin/sh

WGET_OPTS="-q"

branch=$(git symbolic-ref -q HEAD 2>/dev/null)
branch=${branch##refs/heads/}
branch=${branch:-master}
commit="$(git rev-parse --short HEAD 2>/dev/null)"

echo "Current branch: ${branch}"
echo "Current commit: ${commit}"


download()
{
	url="$1"
	out="$2"

	echo "${url} --> ${out} ..."
	if wget ${WGET_OPTS} "${url}" -O "${out}" ; then
		echo "OK"
		exit 0
	fi
	rm -f "${out}"
	echo "FAILED"
}


filename="$1"

if [ -f "${filename}" ] ; then
	echo "File ${filename} already downloaded"
	exit 0
fi

download "https://download.openpaper.work/data/paperwork/${branch}_${commit}/${filename}" "${filename}"

echo "[FALLBACK]"
download "https://download.openpaper.work/data/paperwork/${branch}_latest/${filename}" "${filename}"

echo "[FALLBACK]"
download "https://download.openpaper.work/data/paperwork/master_latest/${filename}" "${filename}"

echo "FAILED: Unable to download ${filename}"
exit 1
