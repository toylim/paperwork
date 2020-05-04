import datetime
import locale
import logging

import openpaperwork_core
import openpaperwork_core.promise

from ... import _


LOGGER = logging.getLogger(__name__)
HELP_FILES = (
    (_("Introduction"), "intro"),
    (_("User manual"), "usage"),
)
LABEL = (_("Documentation"), "#ffffffffffff")


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def __init__(self):
        super().__init__()
        self.doc_urls_to_names_to_urls = {}
        self.doc_urls_to_names = {}
        self.thumbnails = {}

    def get_interfaces(self):
        return [
            'doc_labels',
            'document_storage',
            'help_documents',
            'thumbnail',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'page_img',
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
            {
                'interface': 'thumbnailer',
                'defaults': ['paperwork_backend.model.thumbnail'],
            },
        ]

    def help_get_files(self):
        return HELP_FILES

    def help_get_file(self, name):
        lang = "en"
        try:
            lang = locale.getdefaultlocale()[0][:2]
            LOGGER.info("User language: %s", lang)
        except Exception as exc:
            LOGGER.error(
                "get_documentation(): Failed to figure out locale."
                " Will default to English",
                exc_info=exc
            )
        if lang == "en":
            docs = [name + '.pdf']
        else:
            docs = ['translated_{}_{}.pdf'.format(name, lang), name + ".pdf"]

        for doc in docs:
            url = self.core.call_success(
                "resources_get_file", "paperwork_gtk.model.help.out", doc
            )
            if url is None:
                LOGGER.warning("No documentation '%s' found", doc)
            else:
                LOGGER.info("Documentation '%s': %s", doc, url)
                self.doc_urls_to_names_to_urls[name] = url
                self.doc_urls_to_names[url] = name
                return url
        LOGGER.error("Failed to find documentation '%s'", name)
        return None

    def doc_id_to_url(self, doc_id, existing=True):
        if not doc_id.startswith("help_"):
            return None
        name = doc_id[len("help_"):]
        return self.help_get_file(name)

    def doc_get_date_by_id(self, doc_id):
        if not doc_id.startswith("help_"):
            return None
        return datetime.datetime.now()

    def thumbnail_get_doc_promise(self, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return None
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self.thumbnail_get_doc, args=(doc_url,)
        )

    def thumbnail_get_doc(self, doc_url):
        return self.thumbnail_get_page(doc_url, page_idx=0)

    def thumbnail_get_page(self, doc_url, page_idx):
        if doc_url not in self.doc_urls_to_names:
            return None
        if page_idx != 0:
            return None

        if doc_url in self.thumbnails:
            url = self.thumbnais[doc_url]
            return self.core.call_success("url_to_pillow", url)

        page_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        assert(page_url is not None)
        img = self.core.call_success("url_to_pillow", page_url)
        img = self.core.call_success("thumbnail_from_img", img)

        (self.thumbnail_url, fd) = self.core.call_success(
            "fs_mktemp", prefix="thumbnail_help_intro", suffix=".jpeg",
            mode="wb"
        )
        fd.close()
        self.core.call_success(
            "pillow_to_url", img, self.thumbnail_url,
            format='JPEG', quality=0.85
        )
        return img

    def doc_get_mtime_by_url(self, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return
        return datetime.datetime(year=1971, month=1, day=1).timestamp()

    def doc_has_labels_by_url(self, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return None
        return True

    def doc_get_labels_by_url(self, out: set, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return
        out.add(LABEL)

    def doc_get_labels_by_url_promise(self, out: list, doc_url):
        if doc_url not in self.doc_urls_to_names:
            return

        def get_labels(labels=None):
            if labels is None:
                labels = set()
            labels.add(LABEL)
            return labels

        promise = openpaperwork_core.promise.Promise(
            self.core, get_labels
        )
        out.append(promise)

    def doc_add_label_by_url(self, doc_url, label, color=None):
        if doc_url not in self.doc_urls_to_names:
            return None
        return True

    def help_labels_get_all(self, out: set):
        out.add(LABEL)
