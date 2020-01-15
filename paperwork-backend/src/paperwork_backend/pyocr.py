import gettext
import glob
import locale
import logging
import os

import pycountry
import pyocr
import pyocr.builders

import openpaperwork_core

from . import util


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
    os.makedirs(tessdatadir, exist_ok=True)

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
    LOGGER.info("System language: {}".format(lang_str))

    attrs = (
        'iso_639_3_code',
        'iso639_3_code',
        'iso639_2T_code',
        'iso639_1_code',
        'terminology',
        'bibliographic',
        'alpha_3',
        'alpha_2',
        'alpha2',
        'name',
    )
    for attr in attrs:
        try:
            r = pycountry.pycountry.languages.get(**{attr: lang_str})
            if r is not None:
                LOGGER.info("OCR language: {}".format(r))
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


def pycountry_to_tesseract(ocr_lang, possibles=None):
    attrs = [
        'iso639_3_code',
        'terminology',
        'alpha_3',
    ]
    for attr in attrs:
        if not hasattr(ocr_lang, attr):
            continue
        if possibles is None or getattr(ocr_lang, attr) in possibles:
            r = getattr(ocr_lang, attr)
            if r is not None:
                return r
    return None


def get_default_ocr_lang(allow_none=False):
    # Try to guess based on the system locale what would be
    # the best OCR language

    ocr_tools = pyocr.get_available_tools()
    if len(ocr_tools) == 0:
        if allow_none:
            return None
        else:
            return DEFAULT_OCR_LANG
    ocr_langs = ocr_tools[0].get_available_languages()

    lang = find_language(allow_none=True)
    if lang is None:
        return None
    lang = pycountry_to_tesseract(lang, ocr_langs)
    if lang is not None:
        return lang
    if allow_none:
        return None
    else:
        return DEFAULT_OCR_LANG


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        init_flatpak()

    def get_interfaces(self):
        return [
            "chkdeps",
            "ocr_settings",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
        ]

    def init(self, core):
        super().init(core)

        ocr_lang = self.core.call_success(
            "config_build_simple",
            "OCR", "Lang", get_default_ocr_lang
        )
        self.core.call_all("config_register", "ocr_lang", ocr_lang)

    def chkdeps(self, out: dict):
        ocr_tools = pyocr.get_available_tools()
        if len(ocr_tools) <= 0:
            out['tesseract']['debian'] = 'tesseract-ocr'
            out['tesseract']['fedora'] = 'tesseract'
            out['tesseract']['gentoo'] = 'app-text/tesseract'
            out['tesseract']['linuxmint'] = 'tesseract-ocr'
            out['tesseract']['raspbian'] = 'tesseract-ocr'
            out['tesseract']['ubuntu'] = 'tesseract-ocr'
        ocr_lang = get_default_ocr_lang(allow_none=True)
        if ocr_lang is None:
            ocr_lang = find_language(allow_none=True)
            if ocr_lang is None:
                ocr_lang = "UNKNOWN"
            else:
                ocr_lang = pycountry_to_tesseract(ocr_lang)
                if ocr_lang is None:
                    ocr_lang = "<PYCOUNTRY ERROR>"
            name = 'tesseract-data-{}'.format(ocr_lang)
            out[name]['debian'] = 'tesseract-ocr-{}'.format(ocr_lang)
            out[name]['fedora'] = 'tesseract-langpack-{}'.format(ocr_lang)
            out[name]['linuxmint'] = 'tesseract-ocr-{}'.format(ocr_lang)
            out[name]['raspbian'] = 'tesseract-ocr-{}'.format(ocr_lang)
            out[name]['ubuntu'] = 'tesseract-ocr-{}'.format(ocr_lang)

    def ocr_get_lang(self):
        return self.core.call_success("config_get", "ocr_lang")

    def ocr_set_lang(self, lang):
        return self.core.call_success(
            "config_set", "ocr_lang", lang
        )
