#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import logging
import uuid

from gi.repository import GLib
from gi.repository import Libinsane

import openpaperwork_core

from paperwork_backend.util import find_language


logger = logging.getLogger(__name__)
RECOMMENDED_SCAN_RESOLUTION = 300


class _ScanTimes(object):
    """
    Helper to find, load and rewrite the scan times stored in the configuration
    """
    __ITEM_2_CONFIG = {
        'calibration': ('Scanner', 'ScanTimeCalibration'),
        'normal': ('Scanner', 'ScanTime'),
        'ocr': ('OCR', 'OCRTime'),
    }

    def __init__(self, core):
        self.core = core
        self.section = self.__ITEM_2_CONFIG['normal'][0]

    def get(self):
        values = {}
        for (k, cfg) in self.__ITEM_2_CONFIG.items():
            value = self.core.call_success(
                "config_get", cfg[0], cfg[1], 60.0
            )
            values[k] = value

    def put(self, values):
        for (k, v) in values.items():
            if k not in self.__ITEM_2_CONFIG:
                logger.warning(
                    "Got timing for '%s' but don't know how to store it", k
                )
                continue
            cfg = self.__ITEM_2_CONFIG[k]
            self.core.call_success("config_put", cfg[0], cfg[1], v)


class _PaperworkScannerCalibration(object):
    def __init__(self, core, section):
        self.core = core
        self.section = section

    def get(self):
        pts = [None] * 4
        pts[0] = self.core.call_success(
            "config_get", "Scanner", "Calibration_Pt_A_X", None
        )
        pts[1] = self.core.call_success(
            "config_get", "Scanner", "Calibration_Pt_A_Y", None
        )
        pts[2] = self.core.call_success(
            "config_get", "Scanner", "Calibration_Pt_B_X", None
        )
        pts[3] = self.core.call_success(
            "config_get", "Scanner", "Calibration_Pt_B_Y", None
        )
        if None in pts:
            # no calibration yet
            return None
        if (pts[0] > pts[2]):
            (pts[0], pts[2]) = (pts[2], pts[0])
        if (pts[1] > pts[3]):
            (pts[1], pts[3]) = (pts[3], pts[1])

        resolution = self.core.call_success(
            "config_get", "Scanner", "Calibration_Resolution", 200
        )

        self.value = (resolution, ((pts[0], pts[1]), (pts[2], pts[3])))

    def put(self, value):
        (resolution, ((pt_a_x, pt_a_y), (pt_b_x, pt_b_y))) = value
        self.core.call_all(
            "config.set", "Scanner", "Calibration_Resolution", resolution
        )
        self.core.call_all(
            "config_put", "Scanner", "Calibration_Pt_A_X", pt_a_x
        )
        self.core.call_all(
            "config.set", "Scanner", "Calibration_Pt_A_Y", pt_a_y
        )
        self.core_call_all(
            "config_put", "Scanner", "Calibration_Pt_B_X", pt_b_x
        )
        self.core.call_all(
            "config_put", "Scanner", "Calibration_Pt_B_Y", pt_b_y
        )


class _PaperworkDate(object):
    def __init__(self, core, section, token,
                 default_value_func=lambda: datetime.datetime.today()):
        self.core = core
        self.section = section
        self.token = token
        self.default_value_func = default_value_func
        self.date_format = "%Y-%m-%d"

    def get(self):
        value = self.core.call_success(
            "config_get", self.section, self.token, None
        )
        if value is None:
            return self.default_value_func()
        return datetime.datetime.strptime(value, self.date_format)

    def put(self, value):
        value = self.value.strftime(self.date_format)
        self.core.call_all("config_put", self.section, self.token, value)


class _PaperworkLangs(object):
    """
    Convenience setting. Gives all the languages used as one dictionary
    """

    def __init__(self, ocr_lang_setting, spellcheck_lang_setting):
        self.ocr_lang_setting = ocr_lang_setting
        self.spellcheck_lang_setting = spellcheck_lang_setting
        self.section = "OCR"

    def get(self):
        ocr_lang = self.ocr_lang_setting.get()
        if ocr_lang is None:
            return None
        return {
            'ocr': ocr_lang,
            'spelling': self.spellcheck_lang_setting.value
        }


def get_default_spellcheck_lang(ocr_lang):
    ocr_lang = ocr_lang.value
    if ocr_lang is None:
        return None

    # Try to guess the lang based on the ocr lang
    lang = find_language(ocr_lang)
    if hasattr(lang, 'iso639_1_code'):
        return lang.iso639_1_code
    if hasattr(lang, 'alpha2'):
        return lang.alpha2
    return lang.alpha_2


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.core = None
        self.settings = {}
        self.values = {}

    def get_interfaces(self):
        return ['paperwork_gtk_config']

    def get_deps(self):
        return {
            'interfaces': [
                ('paperwork_config', ['paperwork_backend.config']),
            ],
        }

    def init(self, core):
        core.call_all(
            'paperwork_config_register', 'main_win_size',
            core.call_success(
                "paperwork_config_build_simple",
                "GUI", "main_win_size", lambda: [1024, 768]
            )
        )
        core.call_all(
            'paperwork_config_register', 'ocr_enabled',
            core.call_success(
                "paperwork_config_build_simple",
                "OCR", "Enabled", lambda: True
            )
        )
        core.call_all(
            'paperwork_config_register', 'result_sorting',
            core.call_success(
                "paperwork_config_build",
                "GUI", "Sorting", lambda: "scan_date"
            )
        )
        core.call_all(
            'paperwork_config_register', 'scanner_calibration',
            _PaperworkScannerCalibration(core, "Scanner")
        )
        core.call_all(
            'paperwork_config_register', 'scanner_devid',
            core.call_success(
                "paperwork_config_build_simple",
                "Scanner", "Device", lambda: None
            )
        )
        core.call_all(
            'paperwork_config_register', 'scanner_resolution',
            core.call_success(
                "paperwork_config_build_simple",
                "Scanner", "Resolution",
                lambda: RECOMMENDED_SCAN_RESOLUTION
            )
        )
        core.call_all(
            'paperwork_config_register', 'scanner_source',
            core.call_success(
                "paperwork_config_build_simple",
                "Scanner", "Source", lambda: None
            )
        )
        core.call_all(
            'paperwork_config_register', 'scanner_has_feeder',
            core.call_success(
                "paperwork_config_build_simple",
                "Scanner", "Has_Feeder", lambda: False
            )
        )
        core.call_all(
            'paperwork_config_register', 'scan_time', _ScanTimes(core)
        )
        core.call_all(
            'paperwork_config_register', 'zoom_level',
            core.call_success(
                "paperwork_config_build_simple",
                "GUI", "zoom_level", lambda: 0.0
            )
        )

        # update detection
        core.call_all(
            'paperwork_config_register', 'check_for_update',
            core.call_success(
                "paperwork_config_build_simple",
                "Update", "check", lambda: False
            )
        )
        core.call_all(
            'paperwork_config_register', 'last_update_check',
            _PaperworkDate(
                core, "Update", "last_check",
                lambda: datetime.datetime(year=1970, month=1, day=1)
            )
        )
        core.call_all(
            'paperwork_config_register', 'last_update_found',
            core.call_success(
                "paperwork_config_build_simple",
                "Update", "last_update_found", lambda: None
            )
        )

        # statistics
        core.call_all(
            'paperwork_config_register', 'send_statistics',
            core.call_success(
                "paperwork_config_build_simple",
                "Statistics", "send", lambda: False
            )
        )
        core.call_all(
            'paperwork_config_register', 'last_statistics_post',
            _PaperworkDate(
                core, "Statistics", "last_post",
                lambda: datetime.datetime(year=1970, month=1, day=1)
            )
        )
        core.call_all(
            'paperwork_config_register', 'uuid',
            core.call_success(
                "paperwork_config_build_simple",
                "Statistics", "uuid", lambda: uuid.getnode()
            )
        )

        spelling_lang_setting = core.call_success(
            "paperwork_config_build_simple",
            "SpellChecking", "Lang",
            lambda: get_default_spellcheck_lang(
                core.call_success("paperwork_config_get", "ocr_lang")
            )
        )
        core.call_all(
            'paperwork_config_register', 'spelling_lang', spelling_lang_setting
        )
        core.call_all(
            'paperwork_config_register', 'langs',
            _PaperworkLangs(
                core.call_success("paperwork_config_get_setting", 'ocr_lang'),
                spelling_lang_setting
            )
        )


def _get_scanner(core, libinsane, devid, preferred_sources=None):
    logger.info("Will scan using %s" % str(devid))

    config_source = core.call_success("paperwork_config_get", "scanner_source")

    dev = libinsane.get_device(devid)
    srcs = {src.get_name(): src for src in dev.get_children()}

    if not preferred_sources:
        src_name = config_source
    else:
        # Favor the source from the configuration if it matches
        # the preferred sources.
        src_name = None
        for possible in preferred_sources:
            if possible.lower() in config_source.lower():
                src_name = [config_source]
                break
        # else find a source that matches the preferred_sources requirement
        if src_name is None:
            for src in srcs.keys():
                for possible in preferred_sources:
                    if possible.lower() in src.lower():
                        src_name = src
                        break
                if src_name is not None:
                    break
        # else default to the config
        if src_name is None:
            src_name = config_source

    src = srcs[src_name]

    resolution = core.call_success(
        "paperwork_config_get", 'scanner_resolution'
    )
    logger.info("Will scan at a resolution of %d", resolution)

    opts = {opt.get_name(): opt for opt in src.get_options()}
    if 'resolution' not in opts:
        logger.warning("Can't set the resolution on this scanner."
                       " Option not found")
    else:
        opts['resolution'].set_value(resolution)

    if 'mode' not in opts:
        logger.warning("Can't set the mode on this scanner. Option not found")
    else:
        opts['mode'] = "Color"

    return (dev, resolution)


def get_scanner(core, libinsane, preferred_sources=None):
    devid = core.call_success("paperwork_config_get", 'scanner_devid')

    try:
        return _get_scanner(core, libinsane, devid, preferred_sources)
    except (KeyError, GLib.Error) as exc:
        logger.warning(
            "Exception while configuring scanner: %s: %s", type(exc), str(exc),
            exc_info=exc
        )
        try:
            # we didn't find the scanner at the given ID
            # but maybe there is only one, so we can guess the scanner to use
            devices = libinsane.list_devices(
                Libinsane.DeviceLocations.ANY
            )
            if len(devices) != 1:
                raise
            logger.info(
                "Will try another scanner id: %s" % devices[0].get_dev_id()
            )
            return _get_scanner(
                core, devices[0].get_dev_id(), preferred_sources
            )
        except GLib.Error:
            # this is a fallback mechanism, but what interest us is the first
            # exception, not the one from the fallback
            raise exc
