import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    # so we can report an accurate document count
    PRIORITY = 1000

    def __init__(self):
        super().__init__()
        self.selection = set()

    def get_interfaces(self):
        return ['doc_selection']

    def doc_selection_reset(self):
        self.selection = set()

    def doc_selection_add(self, doc_id, doc_url):
        self.selection.add((doc_id, doc_url))

    def doc_selection_remove(self, doc_id, doc_url):
        self.selection.remove((doc_id, doc_url))

    def doc_selection_get(self, out: set):
        out.update(self.selection)

    def doc_selection_len(self):
        l = len(self.selection)
        if l == 0:
            return None
        return l

    def doc_selection_in(self, doc_id, doc_url):
        if (doc_id, doc_url) in self.selection:
            return True
        return None
