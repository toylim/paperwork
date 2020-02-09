import gettext
import re

import openpaperwork_core


_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    KEYWORDS = {
        "centrally aligned": _("centrally aligned"),
        "feeder": _("Feeder"),
        "flatbed": _("Flatbed"),
        "left aligned": _("centrally aligned"),
        "right aligned": _("centrally aligned"),
    }

    RE_SPLIT_SOURCE_NAME = [
        re.compile('([()])'),
        re.compile('(\W)'),
    ]

    def get_interfaces(self):
        return ['i18n_scanner']

    def i18n_scanner_source(self, source_name):
        for regex in self.RE_SPLIT_SOURCE_NAME:
            source_name = regex.split(source_name)
            for i in range(0, len(source_name)):
                if source_name[i].lower() in self.KEYWORDS:
                    source_name[i] = self.KEYWORDS[source_name[i].lower()]
            source_name = "".join(source_name)
        return source_name
