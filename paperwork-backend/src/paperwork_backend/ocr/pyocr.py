import gettext
import glob
import locale
import logging
import os

import pycountry
import pyocr
import pyocr.builders

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

DEFAULT_OCR_LANG = "eng"  # if really we can't guess anything


def init_flatpak():
    """
    If we are in Flatpak, we must build a tessdata/ directory using the
    .traineddata files from each locale directory
    """
    tessdata_files = glob.glob("/app/share/locale/*/*.traineddata")
    if len(tessdata_files) <= 0:
        return

    localdir = os.path.expanduser("~/.local")
    base_data_dir = os.getenv(
        "XDG_DATA_HOME",
        os.path.join(localdir, "share")
    )
    tessdatadir = os.path.join(base_data_dir, "paperwork", "tessdata")

    LOGGER.info("Assuming we are running in Flatpak."
                " Building tessdata directory %s ...", tessdatadir)
    util.rm_rf(tessdatadir)
    util.mkdir_p(tessdatadir)

    os.symlink("/app/share/tessdata/eng.traineddata",
               os.path.join(tessdatadir, "eng.traineddata"))
    os.symlink("/app/share/tessdata/osd.traineddata",
               os.path.join(tessdatadir, "osd.traineddata"))
    os.symlink("/app/share/tessdata/configs",
               os.path.join(tessdatadir, "configs"))
    os.symlink("/app/share/tessdata/tessconfigs",
               os.path.join(tessdatadir, "tessconfigs"))
    for tessdata in tessdata_files:
        LOGGER.info("%s found", tessdata)
        os.symlink(tessdata, os.path.join(tessdatadir,
                                          os.path.basename(tessdata)))
    os.environ['TESSDATA_PREFIX'] = tessdatadir
    LOGGER.info("Tessdata directory ready")


def find_language(lang_str=None, allow_none=False):
    if lang_str is None:
        lang_str = locale.getdefaultlocale()[0]
        if lang_str is None and not allow_none:
            LOGGER.warning("Unable to figure out locale. Assuming english !")
            return find_language(DEFAULT_OCR_LANG)
        if lang_str is None:
            LOGGER.warning("Unable to figure out locale !")
            return None

    lang_str = lang_str.lower()
    if "_" in lang_str:
        lang_str = lang_str.split("_")[0]

    try:
        r = pycountry.pycountry.languages.get(name=lang_str.title())
        if r is not None:
            return r
    except (KeyError, UnicodeDecodeError):
        pass

    attrs = (
        'iso_639_3_code',
        'iso639_3_code',
        'iso639_2T_code',
        'iso639_1_code',
        'terminology',
        'bibliographic',
        'alpha_3',
        'alpha_2',
        'alpha2'
    )
    for attr in attrs:
        try:
            r = pycountry.pycountry.languages.get(**{attr: lang_str})
            if r is not None:
                return r
        except (KeyError, UnicodeDecodeError):
            pass

    if allow_none:
        LOGGER.warning("Unknown language [{}]".format(lang_str))
        return None
    if lang_str is not None and lang_str == DEFAULT_OCR_LANG:
        raise Exception("Unable to find language !")
    LOGGER.warning("Unknown language [{}]. Switching back to english".format(
        lang_str
    ))
    return find_language(DEFAULT_OCR_LANG)


def get_default_ocr_lang():
    # Try to guess based on the system locale what would be
    # the best OCR language

    ocr_tools = pyocr.get_available_tools()
    if len(ocr_tools) == 0:
        return DEFAULT_OCR_LANG
    ocr_langs = ocr_tools[0].get_available_languages()

    lang = find_language()
    if hasattr(lang, 'iso639_3_code') and lang.iso639_3_code in ocr_langs:
        return lang.iso639_3_code
    if hasattr(lang, 'terminology') and lang.terminology in ocr_langs:
        return lang.terminology
    return DEFAULT_OCR_LANG


class OcrTransaction(object):
    def __init__(self, plugin, total_expected=-1):
        self.plugin = plugin
        self.core = plugin.core
        self.total_expected = total_expected
        self.count = 0

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        return self.count / self.total_expected

    def add_obj(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        for page_idx in range(0, nb_pages):
            current_boxes = self.core.call_success(
                "page_get_boxes_by_url", doc_url, page_idx
            )
            if current_boxes is not None and len(current_boxes) > 0:
                # there is already some text on this page
                LOGGER.info(
                    "Page %s p%d has already some text. No OCR run",
                    doc_id, page_idx
                )
                self.core.call_one(
                    "schedule", self.core.call_all,
                    "on_progress", "ocr", self._get_progression(),
                    _("Document %s p%d has already some text. No OCR run") % (
                        doc_id, page_idx
                    )
                )
                continue
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_progress", "ocr", self._get_progression(),
                _("Running OCR on document %s page %d") % (
                    doc_id, page_idx
                )
            )
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_ocr_start", doc_id, page_idx
            )
            self.plugin.ocr_page_by_url(doc_url, page_idx)
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_ocr_end", doc_id, page_idx
            )

        self.count += 1

    def upd_obj(self, doc_id):
        # not used here
        self.count += 1

    def del_obj(self, doc_id):
        # not used here
        self.count += 1

    def unchanged_obj(self, doc_id):
        # not used here
        self.count += 1

    def cancel(self):
        pass

    def commit(self):
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "ocr", 1.0
        )


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def __init__(self):
        init_flatpak()

    def get_interfaces(self):
        return [
            "ocr",
            "syncable",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('document_storage', ['paperwork_backend.model.workdir',]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
                ('paperwork_config', ['paperwork_backend.config.file',]),
                ('pillow', [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]),
                ('page_boxes', [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ]),
            ]
        }

    def init(self, core):
        super().init(core)

        ocr_lang = self.core.call_success(
            "paperwork_config_build_simple",
            "OCR", "Lang", get_default_ocr_lang
        )
        self.core.call_all("paperwork_config_register", "ocr_lang", ocr_lang)

    def ocr_page_by_url(self, doc_url, page_idx):
        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        ocr_tool = pyocr.get_available_tools()[0]
        LOGGER.info("Will use tool '%s'" % (ocr_tool.get_name()))

        ocr_lang = self.core.call_success("paperwork_config_get", "ocr_lang")

        img = self.core.call_success("url_to_pillow", page_img_url)

        boxes = ocr_tool.image_to_string(
            img, lang=ocr_lang,
            builder=pyocr.builders.LineBoxBuilder()
        )
        self.core.call_all("page_set_boxes_by_url", doc_url, page_idx, boxes)

    def doc_transaction_start(self, out: list, total_expected=-1):
        # we monitor document transactions just so we can OCR freshly
        # added documents.
        out.append(OcrTransaction(self, total_expected))

    def sync(self, promises):
        # Nothing to do in that case, just here to satisfy the interface
        # 'syncable'
        pass
