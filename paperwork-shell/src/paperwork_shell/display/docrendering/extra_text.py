import openpaperwork_core

from ... import _


class ExtraTextRenderer(object):
    def __init__(self, core):
        self.core = core
        self.parent = None

    def get_preview_output(
                self, doc_id, doc_url, terminal_size=(80, 25),
                page_idx=0
            ):
        if self.parent is not None:
            return self.parent.get_preview_output(
                doc_id, doc_url, terminal_size, page_idx
            )
        return []

    def get_doc_output(self, doc_id, doc_url, terminal_size=(80, 25)):
        out = []
        if self.parent is not None:
            out = self.parent.get_doc_output(
                doc_id, doc_url, terminal_size
            )
        extra_text = []
        self.core.call_all("doc_get_extra_text_by_url", extra_text, doc_url)
        extra_text = "\n".join(extra_text).strip().split("\n")

        if len(extra_text) > 0:
            extra_text = ["", "  " + _("Additional text:")] + extra_text

        return extra_text + out

    def get_page_output(
                self, doc_id, doc_url, page_nb, terminal_size=(80, 25)
            ):
        if self.parent is not None:
            return self.parent.get_page_output(
                doc_id, doc_url, page_nb, terminal_size
            )
        return []

    def get_doc_infos(self, doc_id, doc_url):
        if self.parent is not None:
            return self.parent.get_doc_infos(doc_id, doc_url)
        return {}

    def get_page_infos(self, doc_id, doc_url, page_nb):
        if self.parent is not None:
            return self.parent.get_page_infos(doc_id, doc_url, page_nb)
        return {}


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 11000

    def get_interfaces(self):
        return ['doc_renderer']

    def get_deps(self):
        return [
            {
                'interface': 'extra_text',
                'defaults': ['paperwork_backend.model.extra_text'],
            },
        ]

    def doc_renderer_get(self, out):
        r = ExtraTextRenderer(self.core)
        if len(out) > 0:
            r.parent = out[-1]
        out.append(r)
