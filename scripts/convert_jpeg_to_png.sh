#!/usr/bin/env bash

if [ -z "$2" ] ; then
	echo "Convert all JPEG files in a Paperwork work directory into PNG."
	echo "Requires 'convert' (imagemagick) and 'parallel' (GNU parallel)."
	echo
	echo "Syntax:"
	echo "  $0 <source work directory> <destination work directory>"
	exit 1
fi

in_dir="$1"
out_dir="$2"

cp -R "$in_dir" "$out_dir"

cd "$out_dir"

echo Converting

for jpg in $(find . -name paper\*.jpg | grep -v thumb) ; do
	png=$(echo $jpg | sed s/jpg/png/g)
	echo "convert $jpg $png"
done | parallel --halt now,fail=1 sh -c {}

echo "All converted. Cleaning up"

for jpg in $(find . -name paper\*.jpg | grep -v thumb) ; do
	rm -f $jpg
done

echo "All done !"
