import datetime
import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.url_selected = None
        self.method_radio = None
        self.method_apply_callbacks = {}

    def get_interfaces(self):
        return ['gtk_bug_report_dialog']

    def get_deps(self):
        return [
            {
                'interface': 'external_apps',
                'defaults': [
                    'openpaperwork_core.external_apps.dbus',
                    'openpaperwork_core.external_apps.windows',
                    'openpaperwork_core.external_apps.xdg',
                ],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def _shorten_url(self, url):
        file_name = self.core.call_success("fs_basename", url)
        dir_path = self.core.call_success("fs_dirname", url)
        dir_name = self.core.call_success("fs_basename", dir_path)
        return dir_name + "/" + file_name

    def _format_date(self, date):
        if date is None:
            return _("Now")
        return date.strftime("%c")

    def _format_timestamp(self, date):
        if date is None:
            date = datetime.datetime.now()
        return int(date.timestamp())

    def open_bug_report(self, parent_window):
        self.method_radio = None
        self.method_apply_callbacks = {}
        self.url_selected = None

        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.bug_report", "bug_report.glade"
        )
        self.core.call_all("bug_report_complete", widget_tree)

        widget_tree.get_object("bug_report_toggle_renderer").connect(
            "toggled", self._on_attachment_toggle, widget_tree
        )
        widget_tree.get_object("bug_report_treeview").connect(
            "row-activated", self._on_row_selected, widget_tree
        )
        widget_tree.get_object("bug_report_open_file").connect(
            "clicked", self._open_selected
        )

        model = widget_tree.get_object("bug_report_model")
        model.clear()

        inputs = {}
        self.core.call_all("bug_report_get_attachments", inputs)
        now = datetime.datetime.now()
        for (k, v) in inputs.items():
            v['id'] = k
            v['sort_date'] = v['date'] if v['date'] is not None else now
        inputs = list(inputs.values())
        inputs.sort(key=lambda i: i['sort_date'], reverse=True)
        for i in inputs:
            model.append(
                [
                    False,  # not selected
                    self._format_timestamp(i['date']),
                    self._format_date(i['date']),
                    i['file_type'],
                    i['file_url'],
                    self._shorten_url(i['file_url']),
                    i['file_size'],
                    self.core.call_success("i18n_file_size", i['file_size']),
                    i['id'],
                ]
            )

        dialog = widget_tree.get_object("bug_report_dialog")
        dialog.set_transient_for(parent_window)
        dialog.connect("close", self._on_close)
        dialog.connect("cancel", self._on_close)
        dialog.connect("apply", self._on_apply, widget_tree)

        dialog.set_visible(True)
        self.core.call_all("on_gtk_window_opened", dialog)

    def _on_attachment_toggle(self, cell_renderer, row_path, widget_tree):
        model = widget_tree.get_object("bug_report_model")
        val = not model[row_path][0]
        model[row_path][0] = val
        if val:
            self.core.call_all(
                "on_bug_report_attachment_selected",
                model[row_path][-1], widget_tree
            )
        else:
            self.core.call_all(
                "on_bug_report_attachment_unselected",
                model[row_path][-1], widget_tree
            )

        # check we have at least one entry toggled
        assistant = widget_tree.get_object("bug_report_dialog")
        page = widget_tree.get_object("bug_report_attachment_selector")
        for row in model:
            if row[0]:
                break
        else:
            assistant.set_page_complete(page, False)
            return
        assistant.set_page_complete(page, True)

    def _on_row_selected(self, treeview, row_path, column, widget_tree):
        model = widget_tree.get_object("bug_report_model")
        button = widget_tree.get_object("bug_report_open_file")
        self.url_selected = model[row_path][3]
        button.set_sensitive("://" in self.url_selected)

    def _open_selected(self, button):
        self.core.call_success("external_app_open_file", self.url_selected)

    def bug_report_update_attachment(self, info_id, infos: dict, widget_tree):
        model = self.widget_tree.get_object("bug_report_model")
        for row in model:
            if model[-1] != info_id:
                continue
            if 'date' in infos:
                model[1] = self._format_timestamp(infos['date'])
                model[2] = self._format_date(infos['date'])
            if 'file_type' in infos:
                model[3] = infos['file_type']
            if 'file_url' in infos:
                model[4] = infos['file_url']
                model[5] = self._shorten_url(infos['file_url'])
            if 'file_size' in infos:
                model[6] = infos['file_size']
                model[7] = self.core.call_success(
                    "i18n_file_size", infos['file_size']
                )
            break

    def _on_close(self, dialog):
        dialog.set_visible(False)
        self.core.call_all("on_gtk_window_closed", dialog)

    def bug_report_add_method(
            self, title, description,
            enable_callback, disable_callback, apply_callback,
            widget_tree):
        widget_tree_method = self.core.call_success(
            "gtk_load_widget_tree",
            "openpaperwork_gtk.bug_report", "bug_report_method.glade"
        )
        widget_tree_method.get_object("bug_report_method_title").set_text(
            title
        )
        widget_tree_method.get_object(
            "bug_report_method_description"
        ).set_text(description)

        widget_tree.get_object("bug_report_methods").pack_start(
            widget_tree_method.get_object("bug_report_method"),
            expand=False, fill=False, padding=20
        )

        radio = widget_tree_method.get_object("bug_report_method")
        radio.connect(
            "toggled", self._on_method_toggled, widget_tree,
            enable_callback, disable_callback
        )
        if self.method_radio is None:
            self.method_radio = radio
        else:
            radio.join_group(self.method_radio)
        self.method_radio.set_active(True)
        self.method_apply_callbacks[radio] = apply_callback

    def _on_method_toggled(
            self, radio, widget_tree, enable_callback, disable_callback):
        if radio.get_active():
            enable_callback(widget_tree)
        else:
            disable_callback(widget_tree)

    def bug_report_add_page(self, widget_tree, title, widget):
        return widget_tree.get_object("bug_report_dialog").append_page(widget)

    def bug_report_remove_page(self, widget_tree, page_idx):
        widget_tree.get_object("bug_report_dialog").remove_page(page_idx)

    def _on_apply(self, assistant, widget_tree):
        apply_cb = None
        for radio in self.method_radio.get_group():
            if radio.get_active():
                apply_cb = self.method_apply_callbacks[radio]
                break

        model = widget_tree.get_object("bug_report_model")
        file_urls = [row[4] for row in model if row[0]]
        LOGGER.info("Applying: %s", apply_cb)
        apply_cb(file_urls)
