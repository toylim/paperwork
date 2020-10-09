#!/bin/sh

WGET_OPTS="-q"

if [ -n "${CI_COMMIT_REF_NAME}" ] ; then
	branch="${CI_COMMIT_REF_NAME}"
else
	branch=$(git symbolic-ref -q HEAD)
	echo "Current ref: ${branch}"

	branch=${branch##refs/heads/}
	branch=${branch:-master}

	echo "Current branch: ${branch}"
fi

commit="$(git rev-parse --short HEAD)"
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
