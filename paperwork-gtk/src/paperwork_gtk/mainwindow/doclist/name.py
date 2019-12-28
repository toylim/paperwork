import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_doclist_name',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.maindow.doclist'],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk']['debian'] = 'gir1.2-gtk-3.0'
            out['gtk']['fedora'] = 'gtk3'
            out['gtk']['gentoo'] = 'x11-libs/gtk+'
            out['gtk']['linuxmint'] = 'gir1.2-gtk-3.0'
            out['gtk']['ubuntu'] = 'gir1.2-gtk-3.0'
            out['gtk']['suse'] = 'python-gtk'

    def on_doc_box_creation(self, doc_id, gtk_row, custom_flowbox):
        doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
        doc_date = self.core.call_success("i18n_date_short", doc_date)
        label = Gtk.Label.new(doc_date)
        label.set_visible(True)
        custom_flowbox.add(label)
        custom_flowbox.set_alignment(label, Gtk.Align.START)
