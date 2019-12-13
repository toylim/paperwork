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


class SinglePdfImporter(object):
    def __init__(self, core, file_import, src_file_uri):
        self.core = core
        self.file_import = file_import
        self.src_file_uri = src_file_uri
        self.doc_id = None
        self.doc_url = None

    def _basic_import(self, file_uri):
        (self.doc_id, self.doc_url) = self.core.call_success(
            "doc_pdf_import", file_uri
        )
        self.file_import.new_doc_ids.add(self.doc_id)
        self.file_import.stats[_("PDF")] += 1
        self.file_import.stats[_("Documents")] += 1

    def get_promise(self):
        return openpaperwork_core.promise.Promise(
            self.core, self._basic_import, args=(self.src_file_uri,)
        )


class SinglePdfImporterFactory(object):
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = plugin.core

    @staticmethod
    def get_name():
        return _("Import PDF")

    def is_importable(self, core, file_uri):
        mime = core.call_success("fs_get_mime", file_uri)
        if mime is not None:
            if mime == Plugin.MIME_TYPE:
                return True
            return False
        if file_uri.lower().endswith(self.plugin.FILE_EXTENSION):
            return True

    def make_importer(self, file_import, file_uri):
        return SinglePdfImporter(
            self.core, file_import, file_uri
        )


class Plugin(openpaperwork_core.PluginBase):
    FILE_EXTENSION = ".pdf"
    MIME_TYPE = "application/pdf"

    def get_interfaces(self):
        return [
            "import"
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_pdf_import',
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def get_import_mime_type(self, out: list):
        out.append(("PDF", self.MIME_TYPE))
        out.append((_("PDF folder"), "inode/directory"))

    def get_importer(self, out: list, file_import: FileImport):
        importer = DirectFileImporter(
            self.core, file_import, SinglePdfImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)

        importer = RecursiveFileImporter(
            self.core, file_import, SinglePdfImporterFactory(self)
        )
        if importer.can_import():
            out.append(importer)
