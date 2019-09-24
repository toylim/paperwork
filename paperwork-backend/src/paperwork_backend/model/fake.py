import time

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        # expected in self.docs:
        # [
        #   {
        #     'id': 'some_id',
        #     'url': 'file:///some_work_dir/some_id',
        #     'mtime': 12345,  # unix timestamp
        #     'labels': [(label_name, label_color), ...]
        #     'hash': 12345,  # optional
        #     'text': "pouet",  # optional
        #     'page_boxes: [  # optional
        #       [LineBox, LineBox, ...],  # page 0
        #       [LineBox, LineBox, ...],  # page 1
        #       (...)
        #     ],
        #     'page_imgs':  # optional
        #       (img_url, PIL.Image),  # page 0
        #       (img_url, PIL.Image),  # page 1
        #     ],
        #   },
        #   (...)
        # ]
        self.docs = []
        self.new_doc_idx = 0

    def get_interfaces(self):
        return [
            "document_storage",
            "doc_type",
            "doc_hash",
            "doc_text",
            "doc_labels",
            "page_boxes",
            "pillow",
        ]

    def storage_get_all_docs(self, out: list):
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

    def doc_get_hash_by_url(self, out: list, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if 'hash' in doc:
                    out.append(doc['hash'])

    def doc_get_mtime_by_url(self, out: list, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.append(doc['mtime'])

    def doc_get_nb_pages_by_url(self, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if 'page_boxes' not in doc and 'page_imgs' not in doc:
                    return None
                l_boxes = len(doc['page_boxes']) if 'page_boxes' in doc else 0
                l_imgs = len(doc['page_imgs']) if 'page_imgs' in doc else 0
                return max(l_boxes, l_imgs)
        return None

    def doc_get_text_by_url(self, out: list, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.append(doc['text'])

    def doc_get_labels_by_url(self, out: set, doc_url):
        for doc in self.docs:
            if doc['url'] == doc_url:
                out.update(doc['labels'])

    def doc_add_label_by_url(self, doc_url, label, color=None):
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

    def page_get_boxes_by_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if page_idx >= len(doc['page_boxes']):
                    return None
                return doc['page_boxes'][page_idx]
        return None

    def page_set_boxes_by_url(self, doc_url, page_idx, boxes):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if page_idx >= len(doc['page_boxes']):
                    missing = page_idx + 1 - len(doc['page_boxes'])
                    assert(missing >= 1)
                    doc['page_boxes'] += ([None] * missing)
                doc['page_boxes'][page_idx] = boxes

                text = ""
                for page_boxes in doc['page_boxes']:
                    if page_boxes is None:
                        continue
                    for line_boxes in page_boxes:
                        text += line_boxes.content + "\n"
                doc['text'] = text
        return None

    def page_get_img_url(self, doc_url, page_idx):
        for doc in self.docs:
            if doc['url'] == doc_url:
                if page_idx >= len(doc['page_imgs']):
                    return None
                return doc['page_imgs'][page_idx][0]
        return None

    def url_to_pillow(self, img_url):
        for doc in self.docs:
            for (page_img_url, img) in doc['page_imgs']:
                if page_img_url == img_url:
                    return img
        return None

    def labels_get_all(self, out: set):
        for doc in self.docs:
            out.update(doc['labels'])

    def storage_get_new_doc(self):
        self.new_doc_idx += 1
        doc = {
            'url': 'file:///some_work_dir/{}'.format(self.new_doc_idx),
            'id': str(self.new_doc_idx),
            'mtime': time.time(),
            'labels': [],
        }
        self.docs.append(doc)
        return (doc['id'], doc['url'])
