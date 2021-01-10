"""
Select a scanner if none has been selected yet.
"""
import logging

import Levenshtein

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return []

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
        ]

    def init(self, core):
        super().init(core)

        promise = self.core.call_success("scan_list_scanners_promise")
        promise = promise.then(self._check_dev_id)
        self.core.call_success("scan_schedule", promise)

    def _check_dev_id(self, devs):
        devs = [dev[0] for dev in devs]
        active = self.core.call_success("config_get", "scanner_dev_id")
        if active is not None and active in devs:
            LOGGER.info("Scanner '%s' found. Nothing to do", active)
            return
        LOGGER.info("Scanner '%s' not found", active)
        LOGGER.info("Available scanners: %s", devs)

        if len(devs) <= 0:
            active = None
        elif active is None:
            # pick a scanner at random.
            active = devs[0]
        else:
            LOGGER.info("Previously selected scanner: %s", active)
            # look for the closest scanner ID
            devs = [
                (Levenshtein.distance(dev, active), dev)
                for dev in devs
            ]
            devs.sort()
            active = devs[0][1]

        LOGGER.info("Selected scanner: %s", active)
        self.core.call_success("config_put", "scanner_dev_id", active)
