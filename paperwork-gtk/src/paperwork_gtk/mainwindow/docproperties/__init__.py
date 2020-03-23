import gettext
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['gtk_doc_properties']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "docproperties.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.widget_tree.get_object("docproperties_back").connect(
            "clicked", self._goto_doclist
        )

        self.core.call_all(
            "mainwindow_add", side="left", name="docproperties", prio=0,
            header=self.widget_tree.get_object("docproperties_header"),
            body=self.widget_tree.get_object("docproperties_body"),
        )

    def _goto_doclist(self, *args, **kwargs):
        self.core.call_all(
            "mainwindow_show", side="left", name="doclist"
        )

    def open_doc_properties(self, doc_id, doc_url):
        doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
        doc_txt = self.core.call_success("i18n_date_short", doc_date)
        self.widget_tree.get_object("docproperties_header").set_title(
            _("Properties of %s") % doc_txt
        )
        self.core.call_all(
            "mainwindow_show", side="left", name="docproperties"
        )
