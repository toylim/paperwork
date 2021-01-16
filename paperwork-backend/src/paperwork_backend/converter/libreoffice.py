import logging
import os
import subprocess
import tempfile

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


LIBREOFFICE = [
    r'libreoffice',
    r'soffice.exe',
    r'C:\Program Files\LibreOffice\program\soffice.exe',
]

LIBREOFFICE_ARGS = [
    '--nocrashreport',
    '--nodefault',
    '--nofirststartwizard',
    '--nolockcheck',
    '--nologo',
    '--norestore',
    '--headless',
    '--convert-to', 'pdf',
    '--outdir', '{out_dir}',
    '{in_doc}',
]


def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def which(program):
    if os.path.sep in program:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


class Plugin(openpaperwork_core.PluginBase):
    FILE_TYPES = {
        ("application/msword", "doc"),
        ("application/msword", "dot"),
        ("application/vnd.ms-excel", "xlb"),
        ("application/vnd.ms-excel", "xls"),
        ("application/vnd.ms-excel", "xlt"),
        ("application/vnd.ms-powerpoint", "pps"),
        ("application/vnd.ms-powerpoint", "ppt"),
        ("application/vnd.oasis.opendocument.chart", "odc"),
        ("application/vnd.oasis.opendocument.database", "odb"),
        ("application/vnd.oasis.opendocument.formula", "odf"),
        ("application/vnd.oasis.opendocument.graphics", "odg"),
        ("application/vnd.oasis.opendocument.graphics-template", "otg"),
        ("application/vnd.oasis.opendocument.image", "odi"),
        ("application/vnd.oasis.opendocument.presentation", "odp"),
        (
            "application/vnd.oasis.opendocument.presentation-template",
            "otp"
        ),
        ("application/vnd.oasis.opendocument.spreadsheet", "ods"),
        ("application/vnd.oasis.opendocument.spreadsheet-template", "ots"),
        ("application/vnd.oasis.opendocument.text", "odt"),
        ("application/vnd.oasis.opendocument.text-master", "odm"),
        ("application/vnd.oasis.opendocument.text-template", "ott"),
        ("application/vnd.oasis.opendocument.text-web", "oth"),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".presentation",
            "pptx"
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".slide",
            "sldx"
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".slideshow",
            "ppsx"
        ),
        (
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".template",
            "potx"
        ),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml"
            ".sheet",
            "xlsx"
        ),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml"
            ".template",
            "xltx"
        ),
        (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document",
            "docx"
        ),
        (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.template",
            "dotx"
        ),
    }

    def __init__(self):
        self.libreoffice = None

    def get_interfaces(self):
        return ["converter"]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio']
            },
        ]

    def init(self, core):
        super().init(core)
        for exe in LIBREOFFICE:
            self.libreoffice = which(exe)
            if self.libreoffice is not None:
                break
        LOGGER.info("Libreoffice: %s", self.libreoffice)

    def converter_get_file_types(self, out: set):
        if self.libreoffice is None:
            return
        out.update(self.FILE_TYPES)

    def convert_file_to_pdf(self, doc_file_uri, mime_type, out_pdf_file_url):
        if self.libreoffice is None:
            return None

        file_types = {k: v for (k, v) in self.FILE_TYPES}
        if mime_type not in file_types:
            return None

        LOGGER.info(
            "Converting %s (%s) to %s (PDF)",
            doc_file_uri, mime_type, out_pdf_file_url
        )

        file_name = self.core.call_success("fs_basename", doc_file_uri)
        if "." not in file_name:
            LOGGER.error("No file extension ? %s", doc_file_uri)
            return None
        file_ext = file_name.rsplit(".", 1)[-1]

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            src_file = os.path.join(tmp_dir, "doc." + file_ext)
            dst_file = os.path.join(tmp_dir, "doc.pdf")

            # Assume Libreoffice only supports local files
            self.core.call_success(
                "fs_copy", doc_file_uri,
                self.core.call_success("fs_safe", src_file)
            )

            os.chdir(tmp_dir)
            try:
                args = [
                    x.format(in_doc=src_file, out_dir=tmp_dir)
                    for x in LIBREOFFICE_ARGS
                ]
                popen = subprocess.Popen([self.libreoffice] + args)
                popen.communicate()
            finally:
                os.chdir(cwd)

            self.core.call_success(
                "fs_copy",
                self.core.call_success("fs_safe", dst_file),
                out_pdf_file_url
            )
