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

    def config_put(self, opt, value, *args, **kwargs):
        if opt != "workdir":
            return None
        # Bug report 170: When the work directory has been changed,
        # we have to make sure to drop any reference to it so the user doesn't
        # use it by accident.
        # (keep in mind that self.new_doc = (doc_id, doc_url), and doc_url
        # includes the work directory path)
        self.new_doc = None
        return None

    def get_new_doc(self):
        if self.new_doc is not None:
            if self.core.call_success("is_doc", self.new_doc[1]) is None:
                return self.new_doc
        self.new_doc = self.core.call_success("storage_get_new_doc")
        return self.new_doc
