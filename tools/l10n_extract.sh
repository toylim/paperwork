#!/bin/bash

LANGS="de_DE.UTF-8:de
es_ES.UTF-8:es
fr_FR.UTF-8:fr
oc_FR.UTF-8:oc
uk_UA.UTF-8:uk"

if [ -z "$1" ] || [ -z "$2" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ] ; then
	echo "Usage:"
	echo "  $0 <source_directory> <destination_directory>"
	echo
	echo "Examples:"
	echo "  $0 src/paperwork_gtk l10n"
	echo
	echo "You should probably use 'make l10_extract' instead of calling this script directly"
	exit 1
fi

if ! which intltool-extract > /dev/null 2>&1 ; then
	echo "intl-tool-extract is missing"
	echo "--> sudo apt install intltool"
	exit 2
fi

if ! which xgettext > /dev/null 2>&1 ; then
	echo "xgettext is missing"
	echo "--> sudo apt install gettext"
	exit 2
fi

src_dir="$1"
dst_dir="$2"

src_dir=$(realpath --relative-to=$(pwd) ${src_dir})

while ! [ -d .git ]; do
	if [ "$(pwd)" == "/" ]; then
		echo "Failed to find git repository root"
		echo "Are you in a Git repository ?"
		exit 3
	fi
	# we must place ourselves at the root of the repository so the file
	# paths in the .pot and .po are correct for Weblate
	src_dir="$(basename $(pwd))/${src_dir}"
	cd ..
done

src_dir=$(realpath --relative-to=$(pwd) ${src_dir})

mkdir -p "${dst_dir}"

echo "Extracting strings from Glade files ..."
for glade_file in $(find "${src_dir}" -name \*.glade) ; do
	# intltool-extract expects a relative path as input
	echo "${glade_file} --> .glade.h ..."
	if ! intltool-extract --type=gettext/glade "${glade_file}" > /dev/null; then
		echo "intltool-extract Failed ! Unable to extract strings to translate from .glade files !"
		exit 3
	fi
done

rm -f "${dst_dir}/messages.pot"
echo "Extracting strings from .py and .h files ..."
if ! xgettext -k_ -kN_ --from-code=UTF-8 -o "${dst_dir}/messages.pot" \
		$(find "${src_dir}" -name \*.py) \
		$(find "${src_dir}" -name \*.glade.h) ; then
	echo "xgettext failed ! Unable to extract strings to translate !"
	exit 3
fi

rm -f $(find "${src_dir}" -name \*.glade.h)

for lang in ${LANGS}
do
	locale=$(echo $lang | cut -d: -f1)
	po_file="${dst_dir}/$(echo $lang | cut -d: -f2).po"

	if ! [ -f ${po_file} ]
	then
		echo "messages.pot --> ${po_file} (gen)"
		msginit --no-translator \
			-l ${locale} -i "${dst_dir}/messages.pot" \
			-o ${po_file}
	else
		echo "messages.pot --> ${po_file} (upd)"
		msgmerge -N -U ${po_file} "${dst_dir}/messages.pot"
	fi
	if [ $? -ne 0 ] ; then
		echo "msginit / msgmerge failed ! Unable to create or update .po file !"
		exit 3
	fi
done
