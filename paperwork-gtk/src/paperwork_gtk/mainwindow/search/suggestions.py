import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -2000000

    def __init__(self):
        super().__init__()
        self.widget_tree = None

    def get_interfaces(self):
        return [
            'doc_open',
            'gtk_search_field_completion',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_search_field',
                'defaults': ['paperwork_gtk.mainwindow.search.field'],
            },
            {
                'interface': 'suggestions',
                'defaults': ['paperwork_backend.index.whoosh'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.search", "suggestions.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        suggestion_revealer = self.widget_tree.get_object(
            "suggestions_revealer"
        )
        self.core.call_all("search_field_add", suggestion_revealer)

        self.widget_tree.get_object("button_close").connect(
            "clicked", self._close
        )
        self.widget_tree.get_object("treeview_suggestions").connect(
            "row-activated", self._on_row_activated
        )

    def _get_suggestions(self, query):
        out = set()
        self.core.call_all("suggestion_get", out, query)
        out = list(out)
        out.sort()
        return out

    def _show_suggestions(self, suggestions, query):
        if query != self.core.call_success("search_get"):
            # Text has changed while we were looking for suggestions
            # No point in displaying them now.
            return
        LOGGER.info("%d suggestions found", len(suggestions))
        model = self.widget_tree.get_object("liststore_suggestions")
        model.clear()
        for suggestion in suggestions:
            model.append((suggestion,))
        self.widget_tree.get_object(
            "suggestions_revealer"
        ).set_reveal_child(len(suggestions) > 0)

    def search_by_keywords(self, query):
        self.widget_tree.get_object("liststore_suggestions").clear()

        self.widget_tree.get_object(
            "suggestions_revealer"
        ).set_reveal_child(False)

        if query == "":
            return

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._get_suggestions, args=(query,)
        )
        promise = promise.then(self._show_suggestions, query)
        self.core.call_success(
            "work_queue_add_promise", "doc_search", promise
        )

    def _close(self, *args, **kwargs):
        self.widget_tree.get_object(
            "suggestions_revealer"
        ).set_reveal_child(False)

    def doc_open(self, *args, **kwargs):
        self._close()

    def _on_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        suggestion = model[path][0]
        self.core.call_all("search_set", suggestion)
