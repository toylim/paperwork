import logging
import re

import openpaperwork_core

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    RE_SPLIT_SOURCE_NAME = [
        re.compile(r'([()])'),
        re.compile(r'(\W)'),
    ]

    def __init__(self):
        super().__init__()
        # Need the l10n plugin to be loaded first before getting the
        # translations
        self.keywords = {}

    def get_interfaces(self):
        return ['i18n_scanner']

    def get_deps(self):
        return [
            {
                'interface': 'l10n',
                'defaults': ['openpaperwork_core.l10n.python'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.keywords = {
            "centrally aligned": _("centrally aligned"),
            "feeder": _("Feeder"),
            "flatbed": _("Flatbed"),
            "left aligned": _("left aligned"),
            "right aligned": _("right aligned"),
        }

    def i18n_scanner_source(self, source_name):
        original = source_name

        for regex in self.RE_SPLIT_SOURCE_NAME:
            source_name = regex.split(source_name)
            for i in range(0, len(source_name)):
                if source_name[i].lower() in self.keywords:
                    source_name[i] = self.keywords[source_name[i].lower()]
            source_name = "".join(source_name)

        LOGGER.debug("I18n: %s --> %s", original, source_name)
        return source_name
