import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['nb_pages']

    def doc_get_nb_pages_by_url(self, doc_url):
        out = []
        self.core.call_all("doc_internal_get_nb_pages_by_url", out, doc_url)
        if len(out) <= 0:
            return None
        return max(out)
