import gettext
import logging

import openpaperwork_core
import openpaperwork_core.promise

from . import (
    DirectFileImporter,
    FileImport,
    RecursiveFileImporter
)


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class SingleImgImporter(object):
    def __init__(self, factory, file_import, src_file_uri, transactions):
        self.factory = factory
        self.core = factory.core
        self.file_import = file_import
        self.src_file_uri = src_file_uri
        self.transactions = transactions
        self.doc_id = None
        self.doc_url = None

    def _basic_import(self, file_uri):
        (self.doc_id, self.doc_url) = self.core.call_success(
            "doc_img_import_file_by_id",
            file_uri, self.file_import.active_doc_id
        )
        self.file_import.stats[_("Images")] += 1
        if self.file_import.active_doc_id is None:
            self.file_import.new_doc_ids.add(self.doc_id)
            self.file_import.stats[_("Documents")] += 1
        else:
            self.file_import.upd_doc_ids.add(self.doc_id)
            self.file_import.stats[_("Pages")] += 1

    def get_promise(self):
        promise = openpaperwork_core.promise.Promise(self.core)
        promise = promise.then(self._basic_import, self.src_file_uri)
        for transaction in self.transactions:
            if self.file_import.active_doc_id is None:
                promise = promise.then(
                    openpaperwork_core.promise.ThreadedPromise(
                        self.core, lambda: transaction.add_obj(self.doc_id)
                    )
                )
            else:
                promise = promise.then(
                    openpaperwork_core.promise.ThreadPromise(
                        self.core, lambda: transaction.upd_obj(self.doc_id)
                    )
                )
        return promise


class SingleImgImporterFactory(object):
    def __init__(self, core):
        self.core = core

    @staticmethod
    def get_name():
        return _("Append the image to the current document")

    @staticmethod
    def is_importable(core, file_uri):
        mime = core.call_success("fs_get_mime", file_uri)
        if mime is not None:
            mimes = [mime[1] for mime in Plugin.IMG_MIME_TYPES]
            if mime in mimes:
                return True
            return False
        file_ext = file_uri.split(".")[-1].lower()
        if file_ext in self.plugin.FILE_EXTENSIONS:
            return True

    def make_importer(self, file_import, file_uri, transactions):
        return SingleImgImporter(
            self, file_import, file_uri, transactions
        )


class Plugin(openpaperwork_core.PluginBase):
    IMG_MIME_TYPES = [
        ("BMP", "image/x-ms-bmp"),
        ("GIF", "image/gif"),
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
        ("TIFF", "image/tiff"),
    ]

    FILE_EXTENSIONS = [
        "bmp",
        "gif",
        "jpeg",
        "jpg",
        "png",
        "tiff",
    ]

    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return [
            "import"
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_img_import', ['paperwork_backend.model.img',]),
                ('fs', ['paperwork_backend.fs.gio',]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
            ]
        }

    def get_import_mime_type(self, out: list):
        out += self.IMG_MIME_TYPES

    def get_importer(self, out: list, file_import: FileImport):
        importer = DirectFileImporter(
            self.core, file_import, SingleImgImporterFactory(self.core)
        )
        if importer.can_import():
            out.append(importer)

        importer = RecursiveFileImporter(
            self.core, file_import, SingleImgImporterFactory(self.core)
        )
        if importer.can_import():
            out.append(importer)
