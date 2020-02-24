import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.default_action = None
        self.default_action_args = None
        self.active_doc_id = None
        self.active_doc_url = None

    def get_interfaces(self):
        return [
            'doc_open',
            'gtk_scan_buttons',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
            {
                'interface': 'scan2doc',
                'defaults': ['paperwork_backend.docscan.scan2doc'],
            },
        ]

    def init(self, core):
        super().init(core)

        opt = self.core.call_success(
            "config_build_simple",
            "pageadd", "default_source", lambda: None
        )
        self.core.call_all("config_register", "pageadd_default_source", opt)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageadd", "buttons.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("pageadd_button").connect(
            "clicked", self._on_clicked
        )

        headerbar = self.core.call_success("docview_get_headerbar")
        headerbar.pack_start(self.widget_tree.get_object("pageadd_buttons"))

    def pageadd_buttons_set_source_popover(self, selector):
        self.widget_tree.get_object("pageadd_switch").set_popover(selector)

    def pageadd_set_default_action(self, txt, callback, *args):
        self.default_action = callback
        self.default_action_args = args
        self.widget_tree.get_object("pageadd_button").set_label(txt)
        self.widget_tree.get_object("pageadd_button").set_sensitive(
            self.default_action is not None and self.active_doc_id is not None
        )

    def _on_clicked(self, widget):
        self.default_action(
            self.active_doc_id, self.active_doc_url,
            *self.default_action_args
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc_id = doc_id
        self.active_doc_url = doc_url
        self.widget_tree.get_object("pageadd_button").set_sensitive(
            self.default_action is not None and self.active_doc_id is not None
        )

    def doc_close(self):
        self.active_doc_id = None
        self.active_doc_url = None
        self.widget_tree.get_object("pageadd_button").set_sensitive(False)
