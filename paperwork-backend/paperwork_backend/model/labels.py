import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

LABELS_FILENAME = "labels"


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            "doc_labels",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('fs', ['paperwork_backend.fs.gio']),
            ]
        }

    def doc_get_labels_by_url(self, out, doc_url):
        labels_url = doc_url + "/" + LABELS_FILENAME
        if self.core.call_success("fs_exists", labels_url) is None:
            return
        with self.core.call_success("fs_open", labels_url) as file_desc:
            for line in file_desc.readlines():
                line = line.strip()
                if line == "":
                    continue
                # Expected: ('label', '#rrrrggggbbbb')
                out.append(tuple(x.strip() for x in line.split(",")))
