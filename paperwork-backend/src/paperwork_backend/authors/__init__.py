import json
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['authors']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def authors_get(self, out: dict):
        file_path = self.core.call_success(
            "resources_get_file", "paperwork_backend.authors",
            "AUTHORS.json"
        )
        if file_path is None:
            LOGGER.error("AUTHORS.json is missing !")
            return None
        try:
            with self.core.call_success("fs_open", file_path, 'r') as fd:
                content = fd.read()
        except FileNotFoundError as exc:
            LOGGER.error(
                "AUTHORS.json is missing ! (expected={})".format(file_path),
                exc_info=exc
            )
            return None
        content = json.loads(content)

        for category in content:
            for (category_name, authors) in category.items():
                out[category_name] = authors

        return True
