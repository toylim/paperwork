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
wait()

core.call_all("open_bug_report")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("close_bug_report")
core.call_all("mainwindow_focus")

core.call_all("gtk_show_shortcuts")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_hide_shortcuts")
core.call_all("mainwindow_focus")

core.call_all("gtk_open_layout_settings")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_close_layout_settings")
core.call_all("mainwindow_focus")

core.call_all("gtk_open_advanced_search_dialog")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_close_advanced_search_dialog")
core.call_all("mainwindow_focus")

core.call_all("gtk_open_settings")
wait()
core.call_all("settings_scroll_to_bottom")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("settings_scroll_to_top")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("display_calibration_screen")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("hide_calibration_screen")
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

core.call_all("page_menu_open")
wait()
core.call_all("screenshot_snap_page_action_menu", "file://${OUT_DIR}/page_menu_opened.png")

core.call_all("doc_menu_open")
wait()
core.call_all("screenshot_snap_doc_action_menu", "file://${OUT_DIR}/doc_menu_opened.png")
EOF

echo "Cleaning up the mess ..."
 rm -rf "${TMP_DIR}"
echo "All done !"
