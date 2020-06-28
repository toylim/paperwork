#!/bin/sh

set -e

TMP_DIR="$(mktemp -d --suffix=paperwork)"
echo "Temporary directory: ${TMP_DIR}"

DATA_DIR="${PWD}/data"
OUT_DIR="${PWD}/out"

TEST_DOCS="${DATA_DIR}/paperwork_test-documents.tar.gz"

if ! [ -f ${TEST_DOCS} ] ; then
	echo "Downloading test documents ..."
	wget -q https://download.openpaper.work/paperwork_test_documents.tar.gz \
		-O "${TEST_DOCS}"
fi

mkdir -p "${TMP_DIR}/config"
mkdir -p "${TMP_DIR}/local"
mkdir -p "${TMP_DIR}/papers"

export XDG_CONFIG_HOME="${TMP_DIR}/config"
export XDG_DATA_HOME="${TMP_DIR}/local"
WORKDIR="${TMP_DIR}/papers"

cd "${WORKDIR}"
echo "Extracting test documents ..."
tar -xzf "${TEST_DOCS}"

echo "Updating Paperwork database ..."
paperwork-cli config put workdir str "file://${WORKDIR}"
paperwork-cli sync

echo "Making screenshots ..."
paperwork-gtk plugins add openpaperwork_core.interactive

paperwork-gtk << EOF
wait()
core.call_all("doc_open", "20990307_0000_00", "file://${WORKDIR}/20990307_0000_00")
core.call_all("search_set", "label:contrat conditions generales")
core.call_all("gtk_open_settings")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("close_settings")
core.call_all("mainwindow_focus")
core.call_all("open_doc_properties", "20990307_0000_00", "file://${WORKDIR}/20990307_0000_00")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("docproperties_scroll_to_last")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("mainwindow_show_default", side="left")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_open_app_menu")
wait()
core.call_all("screenshot_snap_app_menu", "file://${OUT_DIR}/app_menu_opened.png")
EOF

echo "Cleaning up the mess ..."
 rm -rf "${TMP_DIR}"
echo "All done !"
