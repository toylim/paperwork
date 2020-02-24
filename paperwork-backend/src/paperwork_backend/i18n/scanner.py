import gettext
import logging
import re

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    KEYWORDS = {
        "centrally aligned": _("centrally aligned"),
        "feeder": _("Feeder"),
        "flatbed": _("Flatbed"),
        "left aligned": _("left aligned"),
        "right aligned": _("centrally aligned"),
    }

    RE_SPLIT_SOURCE_NAME = [
        re.compile(r'([()])'),
        re.compile(r'(\W)'),
    ]

    def get_interfaces(self):
        return ['i18n_scanner']

    def i18n_scanner_source(self, source_name):
        original = source_name

        for regex in self.RE_SPLIT_SOURCE_NAME:
            source_name = regex.split(source_name)
            for i in range(0, len(source_name)):
                if source_name[i].lower() in self.KEYWORDS:
                    source_name[i] = self.KEYWORDS[source_name[i].lower()]
            source_name = "".join(source_name)

        LOGGER.debug("I18n: %s --> %s", original, source_name)
        return source_name
