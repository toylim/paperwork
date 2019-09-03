import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.docs = []

    def get_interfaces(self):
        return [
            "document_storage",
            "doc_type",
            "doc_hash",
            "doc_text",
            "doc_labels",
        ]

    def storage_get_all_docs(self, out):
        out += [
            (doc['id'], doc['url'])
            for doc in self.docs
        ]

    def doc_id_to_url(self, doc_id):
        for doc in self.docs:
            if doc['id'] == doc_id:
                return doc['url']
        return None

    def doc_url_to_id(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                return doc['id']
        return None

    def is_doc(self, doc_url):
        return True

    def doc_get_hash_by_url(self, out, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if 'hash' in doc:
                    out.append(doc['hash'])

    def doc_get_mtime_by_url(self, out, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.append(doc['mtime'])

    def doc_get_nb_pages_by_url(self, doc_url):
        raise NotImplementedError()

    def doc_get_text_by_url(self, out, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.append(doc['text'])

    def doc_get_labels_by_url(self, out, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.update(doc['labels'])

    def doc_add_label(self, doc_url, label, color=None):
        if color is None:
            all_labels = set()
            self.labels_get_all(all_labels)

            for (l, c) in all_labels:
                if l == label:
                    color = c
                    break
            else:
                raise Exception(
                    "label {} provided without color,"
                    " but label is unknown".format(label)
                )

        for doc in self.docs:
            if doc['url'] == doc_url:
                doc['labels'].add((label, color))

    def labels_get_all(self, out):
        for doc in self.docs:
            out.update(doc['labels'])
