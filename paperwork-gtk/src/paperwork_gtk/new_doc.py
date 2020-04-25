import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.new_doc = None

    def get_interfaces(self):
        return ['new_doc']

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
        ]

    def get_new_doc(self):
        if self.new_doc is not None:
            if self.core.call_success("is_doc", self.new_doc[1]) is None:
                return self.new_doc
        self.new_doc = self.core.call_success("storage_get_new_doc")
        return self.new_doc
