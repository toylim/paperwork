import gettext
import logging
import re

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps
import paperwork_backend.sync


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)

# forbid:
# - empty strings
# - strings that contain a comma
RE_FORBIDDEN_LABELS = re.compile("(^$|.*,.*)")


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.active_doc = None

        # self.widget_to_label is used to find the label corresponding to
        # the widget on which the user did click
        self.widget_to_label = {}

        # self.changed_labels contains the label that have been modified
        # (color or text)
        self.changed_labels = {}

        # self.toggled_labels indicates the labels that have been selected or
        # unselected (value = True or False, depending on whether they are
        # now selected or not)
        self.toggled_labels = {}

        # self.new_labels contains the labels that user has just created
        # (but are not yet applied on any document)
        self.new_labels = set()

        # self.deleted_labels contains the labels that the user wants to
        # remove from *all* the documents.
        self.deleted_labels = set()

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_doc_property',
            'screenshot_provider',
            'syncable',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_colors',
                'defaults': ['openpaperwork_gtk.colors'],
            },
            {
                'interface': 'gtk_doc_properties',
                'defaults': ['paperwork_gtk.docproperties'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'screenshot',
                'defaults': ['openpaperwork_gtk.screenshots'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GTK_AVAILABLE:
            # chkdeps() must still be callable
            return

        screen = Gdk.Screen.get_default()
        if screen is None:
            # Gtk.StyleContext() will fail, but chkdeps() must still be
            # callable
            LOGGER.warning(
                "Cannot get style: Gdk.Screen.get_default()"
                " returned None"
            )
            return None

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doc_properties_components_get(self, out: list):
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docproperties", "labels.glade"
        )
        color_widget = self.widget_tree.get_object("new_label_color")
        color_widget.set_rgba(self.core.call_success(
            "gtk_theme_get_color", "theme_bg_color"
        ))
        out.append(self.widget_tree.get_object("listbox_global"))

        self.widget_tree.get_object("new_label_button").connect(
            "clicked", self._on_new_label
        )
        self.widget_tree.get_object("new_label_entry").connect(
            "activate", self._on_new_label
        )
        self.widget_tree.get_object("new_label_entry").connect(
            "changed", self._on_label_txt_changed
        )

    def _update_toggle_img(self, toggle):
        if toggle.get_active():
            image = Gtk.Image.new_from_icon_name(
                "object-select-symbolic",
                Gtk.IconSize.MENU
            )
        else:
            image = Gtk.Image()
        toggle.set_image(image)

    def doc_properties_components_set_active_doc(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

        self.changed_labels = {}
        self.toggled_labels = {}
        self.new_labels = set()
        self.deleted_labels = set()

        self._refresh_list()

    def _refresh_list(self):
        if self.active_doc is None:
            return

        listbox = self.widget_tree.get_object("listbox_labels")
        for widget in list(listbox.get_children()):
            listbox.remove(widget)

        doc_labels = set()
        self.core.call_all(
            "doc_get_labels_by_url", doc_labels, self.active_doc[1]
        )

        labels = set()
        self.core.call_all("labels_get_all", labels)
        labels.update(doc_labels)

        labels = list(labels)
        labels.sort()

        new_labels = list(self.new_labels)
        new_labels.sort()
        labels += new_labels

        doc_labels = {doc_label[0] for doc_label in doc_labels}

        self.widget_to_label = {}

        for old_label in labels:
            if old_label in self.changed_labels:
                new_label = self.changed_labels[old_label]
            else:
                new_label = old_label

            if old_label in self.deleted_labels:
                continue

            active = old_label[0] in doc_labels
            if old_label in self.toggled_labels:
                active = self.toggled_labels[old_label]
            if old_label in self.new_labels:
                # if the label was just created, it must always be active
                active = True

            widget_tree_label = self.core.call_success(
                "gtk_load_widget_tree",
                "paperwork_gtk.mainwindow.docproperties", "label.glade"
            )
            widget_tree_label.get_object("label_label").set_text(new_label[0])

            toggle = widget_tree_label.get_object("toggle_button")
            toggle.set_active(active)
            toggle.set_sensitive(old_label not in self.new_labels)
            self.widget_to_label[toggle] = old_label
            self._update_toggle_img(toggle)
            toggle.connect("toggled", self._on_toggle)

            color = self.core.call_success("label_color_to_rgb", new_label[1])
            color_button = widget_tree_label.get_object("color_button")
            color_button.set_sensitive(old_label not in self.new_labels)
            self.widget_to_label[color_button] = old_label
            color_button.set_rgba(Gdk.RGBA(color[0], color[1], color[2]))
            color_button.connect("color-set", self._on_color_changed)

            delete = widget_tree_label.get_object("delete_button")
            self.widget_to_label[delete] = old_label
            delete.connect("clicked", self._on_delete)

            listbox.add(widget_tree_label.get_object("label_row"))

        listbox.add(self.widget_tree.get_object("row_add_label"))

    def _on_toggle(self, button):
        self._update_toggle_img(button)
        label = self.widget_to_label[button]
        self.toggled_labels[label] = button.get_active()

    def _on_color_changed(self, button):
        color = button.get_rgba()
        color = (color.red, color.green, color.blue)
        color = self.core.call_success("label_color_from_rgb", color)

        old_label = self.widget_to_label[button]
        new_label = (old_label[0], color)

        self.changed_labels[old_label] = new_label

    def _on_delete(self, button):
        label = self.widget_to_label[button]

        if label in self.new_labels:
            self.new_labels.remove(label)
            return

        self.deleted_labels.add(label)
        self._refresh_list()

    def _on_label_txt_changed(self, *args, **kwargs):
        entry = self.widget_tree.get_object("new_label_entry")
        button = self.widget_tree.get_object("new_label_button")
        txt = entry.get_text().strip()

        button.set_sensitive(True)
        valid = True

        all_labels = set()
        self.core.call_all("labels_get_all", all_labels)
        for label in all_labels:
            if label in self.changed_labels:
                all_labels.add(self.changed_labels[label])
        all_labels.update(self.new_labels)
        all_labels = {label[0] for label in all_labels}

        if txt in all_labels:
            valid = False
            button.set_sensitive(False)
        elif RE_FORBIDDEN_LABELS.match(txt) is not None:
            button.set_sensitive(False)
            if txt != "":
                valid = False

        if valid:
            self.core.call_all("gtk_entry_reset_colors", entry)
        else:
            self.core.call_all("gtk_entry_set_colors", entry)

    def _on_new_label(self, *args, **kwargs):
        text = self.widget_tree.get_object("new_label_entry").get_text()
        text = text.strip()
        if text == "":
            LOGGER.info("New label requested, but no text provided")
            return

        color_widget = self.widget_tree.get_object("new_label_color")

        color = color_widget.get_rgba()
        color = (color.red, color.green, color.blue)
        color = self.core.call_success("label_color_from_rgb", color)

        self.new_labels.add((text, color))
        self._refresh_list()

        # reset fields
        self.widget_tree.get_object("new_label_entry").set_text("")
        color_widget.set_rgba(self.core.call_success(
            "gtk_theme_get_color", "theme_bg_color"
        ))

    def doc_properties_components_apply_changes(self, out):
        LOGGER.info("Selected/Unselected labels: %s", self.toggled_labels)
        LOGGER.info("Modified labels: %s", self.changed_labels)
        LOGGER.info("New labels: %s", self.new_labels)
        LOGGER.info("Deleted labels: %s", self.deleted_labels)

        # The document may have been renamed: use out.doc_id instead of
        # self.active_doc
        doc_id = out.doc_id
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        self.active_doc = (doc_id, doc_url)

        if len(self.toggled_labels) > 0:
            for (label, selected) in self.toggled_labels.items():
                if selected:
                    self.core.call_all(
                        "doc_add_label_by_url", doc_url, label[0], label[1]
                    )
                else:
                    self.core.call_all(
                        "doc_remove_label_by_url", doc_url, label[0]
                    )
            out.upd_docs.add(doc_id)

        if len(self.new_labels) > 0:
            for label in self.new_labels:
                self.core.call_all(
                    "doc_add_label_by_url", doc_url, label[0], label[1]
                )
            out.upd_docs.add(doc_id)

        if len(self.changed_labels) <= 0 and len(self.deleted_labels) <= 0:
            return

        all_docs = []
        self.core.call_all("storage_get_all_docs", all_docs)
        all_docs = set(all_docs)

        if len(self.changed_labels) > 0:
            current = 0
            total = len(self.changed_labels) * len(all_docs)

            for (doc_id, doc_url) in all_docs:
                for (old_label, new_label) in self.changed_labels.items():
                    LOGGER.info(
                        "Changing label %s into %s on document %s",
                        old_label, new_label, doc_id
                    )
                    self.core.call_all(
                        "on_progress", "label_upd", current / total,
                        _("Changing label %s into %s on document %s") % (
                            old_label, new_label, doc_id
                        )
                    )
                    current += 1
                    doc_labels = set()
                    self.core.call_all(
                        "doc_get_labels_by_url", doc_labels, doc_url
                    )
                    if old_label not in doc_labels:
                        continue
                    out.upd_docs.add(doc_id)
                    self.core.call_all(
                        "doc_remove_label_by_url", doc_url, old_label[0]
                    )
                    self.core.call_all(
                        "doc_add_label_by_url", doc_url,
                        new_label[0], new_label[1]
                    )
            self.core.call_all("on_progress", "label_upd", 1.0)

        if len(self.deleted_labels) > 0:
            current = 0
            total = len(self.deleted_labels) * len(all_docs)

            for (doc_id, doc_url) in all_docs:
                for old_label in self.deleted_labels:
                    LOGGER.info(
                        "Deleting label %s from document %s",
                        old_label, doc_id
                    )
                    self.core.call_all(
                        "on_progress", "label_del", current / total,
                        _("Deleting label %s from document %s") % (
                            old_label, doc_id
                        )
                    )
                    current += 1
                    doc_labels = set()
                    self.core.call_all(
                        "doc_get_labels_by_url", doc_labels, doc_url
                    )
                    if old_label not in doc_labels:
                        continue
                    out.upd_docs.add(doc_id)
                    self.core.call_all(
                        "doc_remove_label_by_url", doc_url, old_label[0]
                    )
            self.core.call_all("on_progress", "label_del", 1.0)

    def doc_properties_components_cancel_changes(self):
        self.doc_properties_components_set_active_doc(*self.active_doc)

    def doc_transaction_start(self, out: list, total_expected=-1):
        class RefreshTransaction(paperwork_backend.sync.BaseTransaction):
            priority = -100000

            def commit(s):
                if self.active_doc is None:
                    return
                self.core.call_one("mainloop_schedule", self._refresh_list)

        out.append(RefreshTransaction(self.core, total_expected))

    def sync(self, promises: list):
        pass

    def on_all_labels_loaded(self):
        self._refresh_list()

    def screenshot_snap_all_doc_widgets(self, out_dir):
        if self.widget_tree is None:
            return
        self.core.call_success(
            "screenshot_snap_widget",
            self.widget_tree.get_object("listbox_global"),
            self.core.call_success(
                "fs_join", out_dir, "doc_labels.png"
            ),
            margins=(10, 10, -100, -400)
        )
