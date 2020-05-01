import datetime
import gettext
import logging
import time

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

# GtkListBox doesn't scale well with too many elements
# --> by default we only display 50 documents, and only extend the list
# as needed
NB_DOCS_PER_PAGE = 50


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.doclist = None

        self.scrollbar = None
        self._scrollbar_last_value = -1

        self.docs = []
        self.doc_visibles = 0
        self.row_to_doc = {}
        self.docid_to_row = {}
        self.docid_to_widget_tree = {}

        self.last_date = datetime.datetime(year=1, month=1, day=1)

        self.active_doc = (None, None)
        self.previous_doc = (None, None)

        self.main_actions = []
        self.doc_actions = None

        self.selection_multiple = False

        # the following boolean is a dirty hack to ignore the signal 'toggle'
        # when we toggle the checkbox ourselves (if another plugin
        # calls doc_selection_add() for instance)
        self._toggling = False

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_actions',
            'doc_open',
            'doc_selection',
            'docs_actions',
            'drag_and_drop_destination',
            'gtk_app_menu',
            'gtk_doclist',
            'screenshot_provider',
            'search_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_drag_and_drop',
                'defaults': ['paperwork_gtk.gesture.drag_and_drop'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_widget_flowlayout',
                'defaults': ['paprwork_gtk.widget.flowlayout'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.doclist", "doclist.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", "doclist.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.doc_actions = Gio.Menu.new()

        self.doclist = self.widget_tree.get_object("doclist_listbox")
        self.core.call_all(
            "mainwindow_add", side="left", name="doclist", prio=10000,
            header=self.widget_tree.get_object("doclist_header"),
            body=self.widget_tree.get_object("doclist_body"),
        )
        self.core.call_all(
            "mainwindow_add", side="left", name="doclist_selection_multiple",
            prio=-100000,
            header=self.widget_tree.get_object(
                "doclist_header_selection_multiple"
            ),
            body=None
        )

        self.vadj = self.widget_tree.get_object(
            "doclist_scroll"
        ).get_vadjustment()
        self.vadj.connect("value-changed", self._on_scrollbar_value_changed)

        self.doclist.connect("row-activated", self._on_row_activated)
        self.doclist.connect("drag-motion", self._on_drag_motion)
        self.doclist.connect("drag-leave", self._on_drag_leave)

        self.widget_tree.get_object("doclist_new_doc").connect(
            "clicked", self._on_new_doc
        )

        self.widget_tree.get_object(
            "doclist_back_to_selection_single"
        ).connect("clicked", lambda button: self.core.call_all(
            "gtk_switch_to_doc_selection_single"
        ))

        self.menu_model = self.widget_tree.get_object("doclist_menu_model")
        self.selection_multiple_menu_model = self.widget_tree.get_object(
            "doclist_selection_multiple_menu_model"
        )

        self.core.call_all("drag_and_drop_page_enable", self.doclist)

        self.core.call_one(
            "mainloop_schedule", self.core.call_all, "on_doclist_initialized"
        )

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doclist_add(self, widget, vposition):
        body = self.widget_tree.get_object("doclist_body")
        body.add(widget)
        body.reorder_child(widget, vposition)

    def _on_new_doc(self, button):
        new_doc = self.core.call_success("get_new_doc")
        self.core.call_all("doc_open", *new_doc)
        self.doclist_show(self.docs, show_new=True)

    def _doclist_clear(self):
        start = time.time()

        for child in self.doclist.get_children():
            self.doclist.remove(child)

        stop = time.time()

        LOGGER.info(
            "%d documents cleared in %dms",
            self.doc_visibles, (stop - start) * 1000
        )

    def doclist_clear(self):
        self._doclist_clear()
        self.last_date = datetime.datetime(year=1, month=1, day=1)
        self.doc_visibles = 0
        self.row_to_doc = {}
        self.docid_to_row = {}
        self.docid_to_widget_tree = {}

    def _add_date_box(self, name, txt):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", name
        )
        widget_tree.get_object("date_label").set_text(txt)
        row = widget_tree.get_object("date_box")
        self.doclist.insert(row, -1)

    def _toggle_doc(self, button, doc_id, doc_url):
        if button.get_active():
            self.core.call_all("doc_selection_add", doc_id, doc_url)
        else:
            self.core.call_all("doc_selection_remove", doc_id, doc_url)

    def _add_doc_box(self, doc_id, doc_url, box="doc_box.glade", new=False):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.doclist", box
        )

        doc_box = widget_tree.get_object("doc_box")

        flowlayout = self.core.call_success(
            "gtk_widget_flowlayout_new", spacing=(3, 3)
        )
        flowlayout.set_visible(True)
        doc_box.pack_start(flowlayout, expand=True, fill=True, padding=0)
        doc_box.reorder_child(flowlayout, 1)

        self.core.call_all(
            "on_doc_box_creation", doc_id, widget_tree, flowlayout
        )

        doc_actions = widget_tree.get_object("doc_actions")
        if new:
            doc_actions.set_visible(False)
        else:
            widget_tree.get_object("doc_actions_menu").set_menu_model(
                self.doc_actions
            )

        for action in self.main_actions:
            button = self.core.call_success(
                "gtk_load_widget_tree",
                "paperwork_gtk.mainwindow.doclist", "main_action.glade"
            )
            button.get_object("doc_main_action_image").set_from_icon_name(
                action['icon_name'], Gtk.IconSize.MENU
            )
            button.get_object("doc_main_action").set_tooltip_text(
                action['txt']
            )
            button.get_object("doc_main_action").connect(
                "clicked", lambda _: action['callback']()
            )
            widget_tree.get_object("doc_actions").pack_start(
                button.get_object("doc_main_action"),
                expand=True, fill=True, padding=0
            )

        widget_tree.get_object("doc_box_selector").set_visible(
            self.selection_multiple
        )
        widget_tree.get_object("doc_box_selector").set_active(
            self.core.call_success("doc_selection_in", doc_id, doc_url)
            is not None
        )
        widget_tree.get_object("doc_box_selector").connect(
            "toggled", self._toggle_doc, doc_id, doc_url
        )

        row = widget_tree.get_object("doc_listbox")
        self.row_to_doc[row] = (doc_id, doc_url)
        self.docid_to_row[doc_id] = row
        self.docid_to_widget_tree[doc_id] = widget_tree
        self.doclist.insert(row, -1)

    def doclist_extend(self, nb_docs):
        start = time.time()

        docs = self.docs[
            self.doc_visibles:self.doc_visibles + nb_docs
        ]
        LOGGER.info(
            "Adding %d documents to the document list (%d-%d)",
            len(docs), self.doc_visibles, self.doc_visibles + nb_docs
        )

        for (doc_id, doc_url) in docs:
            doc_date = self.core.call_success("doc_get_date_by_id", doc_id)

            if doc_date.year != self.last_date.year:
                doc_year = self.core.call_success(
                    "i18n_date_long_year", doc_date
                )
                self._add_date_box("year_box.glade", doc_year)

            if (doc_date.year != self.last_date.year or
                    doc_date.month != self.last_date.month):
                doc_month = self.core.call_success(
                    "i18n_date_long_month", doc_date
                )
                self._add_date_box("month_box.glade", doc_month)

            self.last_date = doc_date

            self._add_doc_box(doc_id, doc_url)

        self.doc_visibles = min(len(self.docs), self.doc_visibles + nb_docs)

        stop = time.time()

        LOGGER.info(
            "%d documents shown in %dms (%d displayable)",
            len(docs), (stop - start) * 1000, len(self.docs)
        )

        return len(docs)

    def doclist_show(self, docs, show_new=True):
        self.doclist_clear()

        scroll = (self.docs != docs)
        self.docs = docs

        if show_new:
            new_doc = self.core.call_success("get_new_doc")
            self._add_doc_box(*new_doc, new=True)

        self.doclist_extend(NB_DOCS_PER_PAGE)
        self._reselect_current_doc(scroll=scroll)

    def on_search_start(self, query):
        spinner = self.widget_tree.get_object("doclist_spinner")
        spinner.set_visible(True)
        spinner.start()

    def on_search_results(self, query, docs):
        self.doclist_show(docs, show_new=(query == ""))
        spinner = self.widget_tree.get_object("doclist_spinner")
        spinner.set_visible(False)
        spinner.stop()

    def doc_close(self):
        self.active_doc = (None, None)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)
        self._reselect_current_doc(scroll=False)

    def _show_doc_id(self, doc_id):
        row = self.docid_to_row.get(doc_id)
        while row is None:
            if self.doclist_extend(NB_DOCS_PER_PAGE) <= 0:
                break
            row = self.docid_to_row.get(doc_id)
        return row

    def _reselect_current_doc(self, scroll=True):
        (doc_id, doc_url) = self.active_doc

        if doc_id not in self.docid_to_row:
            LOGGER.info(
                "Document %s not found in the document list", doc_id
            )
            self.vadj.set_value(self.vadj.get_lower())
            return

        row = self._show_doc_id(doc_id)
        assert(row is not None)
        self.doclist.select_row(row)

        if (self.previous_doc[0] is not None and
                self.previous_doc[0] in self.docid_to_widget_tree):
            widget_tree = self.docid_to_widget_tree[self.previous_doc[0]]
            widget_tree.get_object("doc_actions").set_visible(False)

        if ((not self.selection_multiple) and
                self.core.call_success("is_doc", doc_url) is not None and
                doc_id in self.docid_to_widget_tree):
            widget_tree = self.docid_to_widget_tree[doc_id]
            widget_tree.get_object("doc_actions").set_visible(True)

        self.previous_doc = self.active_doc

        if not scroll:
            return

        handler_id = None

        def scroll_to_row(row, allocation):
            adj = allocation.y
            adj -= self.vadj.get_page_size() / 2
            adj += allocation.height / 2
            min_val = self.vadj.get_lower()
            if adj < min_val:
                adj = min_val
            self.vadj.set_value(adj)
            row.disconnect(handler_id)

        handler_id = row.connect("size-allocate", scroll_to_row)

    def _on_scrollbar_value_changed(self, vadj):
        lower = vadj.get_lower()
        upper = vadj.get_upper() - lower
        value = (
            vadj.get_value() +
            vadj.get_page_size() -
            lower
        ) / upper

        if value < 0.95:
            return

        if self._scrollbar_last_value == vadj.get_value():
            # Previous extend call hasn't been taken into account yet
            return

        self.doclist_extend(NB_DOCS_PER_PAGE)
        self._scrollbar_last_value = vadj.get_value()

    def _doc_open(self, doc_id, doc_url):
        if self.active_doc[0] == doc_id:
            return
        LOGGER.info("Opening document %s (%s)", doc_id, doc_url)
        self.core.call_all("doc_open", doc_id, doc_url)

    def _on_row_activated(self, list_box, row):
        (doc_id, doc_url) = self.row_to_doc[row]
        self._doc_open(doc_id, doc_url)

    def menu_app_append_item(self, item):
        # they are actually the same menu
        self.doclist_menu_append_item(item)

    def menu_app_append_submenu(self, label, menu):
        # they are actually the same menu
        self.doclist_menu_append_submenu(label, menu)

    def doclist_menu_append_item(self, item):
        self.menu_model.append_item(item)

    def doclist_menu_append_submenu(self, label, menu):
        self.menu_model.append_submenu(label, menu)

    def docs_menu_append_item(self, item):
        self.selection_multiple_menu_model.append_item(item)

    def docs_menu_append_submenu(self, label, menu):
        self.selection_multiple_menu_model.append_submenu(label, menu)

    def add_doc_action(self, action_label, action_name):
        self.doc_actions.append(action_label, action_name)

    def add_doc_main_action(self, icon_name, txt, callback):
        self.main_actions.append({
            "icon_name": icon_name,
            "txt": txt,
            "callback": callback,
        })

    def _on_drag_motion(self, widget, drag_context, x, y, time):
        widget.drag_unhighlight_row()
        row = widget.get_row_at_y(y)
        if row is not None:
            widget.drag_highlight_row(row)

    def _on_drag_leave(self, widget, drag_context, time):
        widget.drag_unhighlight_row()

    def drag_and_drop_get_destination(self, widget, x, y):
        if self.doclist != widget:
            return None
        row = self.doclist.get_row_at_y(y)
        if row is None:
            LOGGER.warning("No row at %d. Can't get drop destination", y)
            return None
        (doc_id, doc_url) = self.row_to_doc[row]
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0
        return (doc_id, doc_url, nb_pages)

    def gtk_open_app_menu(self):
        self.widget_tree.get_object("doclist_menu").clicked()

    def screenshot_snap_app_menu(self, out_file):
        widget = self.widget_tree.get_object("doclist_menu")

        if widget.get_popover() is not None:
            popover = widget.get_popover()
            if popover.get_visible() and popover.is_drawable():
                widget = popover

        self.core.call_success(
            "screenshot_snap_widget",
            widget, out_file,
            margins=(50, 30, 50, 30)
        )

    def screenshot_snap_all_doc_widgets(self, out_dir):
        self.core.call_success(
            "screenshot_snap_widget",
            self.widget_tree.get_object("doclist_new_doc"),
            self.core.call_success("fs_join", out_dir, "doc_new_button.png"),
            margins=(30, 30, 30, 30)
        )

        self.screenshot_snap_app_menu(
            self.core.call_success("fs_join", out_dir, "app_menu.png")
        )

        if self.active_doc[0] is None:
            return
        widget_tree = self.docid_to_widget_tree[self.active_doc[0]]
        self.core.call_success(
            "screenshot_snap_widget", widget_tree.get_object("doc_actions"),
            self.core.call_success(
                "fs_join", out_dir, "doc_properties_button.png"
            ),
            margins=(50, 50, 50, 50)
        )

    def _set_all_selector_visibility(self, visible):
        for widget_tree in self.docid_to_widget_tree.values():
            checkbox = widget_tree.get_object("doc_box_selector")
            checkbox.set_visible(visible)

    def gtk_switch_to_doc_selection_single(self):
        self.core.call_all(
            "mainwindow_show", side="left", name="doclist"
        )
        self._set_all_selector_visibility(False)
        self.selection_multiple = False
        self._reselect_current_doc(scroll=False)

    def gtk_switch_to_doc_selection_multiple(self):
        self.core.call_all(
            "mainwindow_show", side="left", name="doclist_selection_multiple"
        )
        if not self.selection_multiple:
            self.core.call_all("doc_selection_reset")
        self.selection_multiple = True
        self._set_all_selector_visibility(True)
        self._reselect_current_doc(scroll=False)

    def doc_selection_reset(self):
        self._update_count()

        self._toggling = True
        try:
            for widget_tree in self.docid_to_widget_tree.values():
                checkbox = widget_tree.get_object("doc_box_selector")
                checkbox.set_active(False)
        finally:
            self._toggling = False

    def doc_selection_add(self, doc_id, doc_url):
        self._update_count()

        if self._toggling:
            return
        self._toggling = True
        try:
            widget_tree = self.docid_to_widget_tree.get(doc_id, None)
            if widget_tree is None:
                return
            checkbox = widget_tree.get_object("doc_box_selector")
            if not checkbox.get_active():
                checkbox.set_active(True)
        finally:
            self._toggling = False

    def doc_selection_remove(self, doc_id, doc_url):
        self._update_count()

        if self._toggling:
            return
        self._toggling = True
        try:
            widget_tree = self.docid_to_widget_tree.get(doc_id, None)
            if widget_tree is None:
                return
            checkbox = widget_tree.get_object("doc_box_selector")
            if checkbox.get_active():
                checkbox.set_active(False)
        finally:
            self._toggling = False

    def _update_count(self):
        count = self.core.call_success("doc_selection_len")
        if count is None:
            count = 0
        self.widget_tree.get_object(
            "doclist_selection_multiple_nb_docs"
        ).set_text(_("%d documents") % count)
