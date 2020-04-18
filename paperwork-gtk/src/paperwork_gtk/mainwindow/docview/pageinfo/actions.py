import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_page = None
        self.button_edit = None

    def get_interfaces(self):
        return [
            'doc_open',
            'page_actions',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'backend_readonly',
                'defaults': ['paperwork_gtk.readonly'],
            },
            {
                'interface': 'gtk_docview_pageinfo',
                'defaults': ['paperwork_gtk.mainwindow.docview.pageinfo'],
            },
            {
                'interface': 'gtk_page_editor',
                'defaults': ['paperwork_gtk.mainwindow.pageeditor'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageinfo",
            "actions.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.menu_model = self.widget_tree.get_object("page_menu_model")

        self.button_edit = self.widget_tree.get_object("page_action_edit")
        self.button_edit.connect(
            "clicked", self._on_edit
        )

        self.core.call_success(
            "page_info_add_right", self.widget_tree.get_object("page_actions")
        )

        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_page_menu_ready"
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def _set_sensitivity(self, sensitive):
        self.button_edit.set_sensitive(sensitive)
        self.core.call_all(
            "on_widget_busyness_changed", self.button_edit, sensitive
        )

    def on_backend_readonly(self):
        self._set_sensitivity(False)

    def on_backend_readwrite(self):
        self._set_sensitivity(True)

    def on_page_shown(self, page_idx):
        self.active_page = page_idx

    def _on_edit(self, button):
        self.core.call_all(
            "gtk_open_page_editor", *self.active_doc, self.active_page
        )

    def page_menu_append_item(self, item):
        self.menu_model.append_item(item)
