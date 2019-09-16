import datetime
import logging
import os

import openpaperwork_core
import openpaperwork_core.promise

from . import (
    OpenpaperHttp,
    PeriodicTask
)
from .. import _version


LOGGER = logging.getLogger(__name__)

UPDATE_SERVER = ("https", "openpaper.work")
UPDATE_CHECK_INTERVAL = datetime.timedelta(days=7)
UPDATE_PATH = "/beacon/latest"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.periodic = PeriodicTask(
            "update",
            datetime.timedelta(days=7),
            self.update_check,
            self.update_compare
        )
        self.http = OpenpaperHttp(
            "update", "https", "openpaper.work", "/beacon/latest"
        )

    def get_interfaces(self):
        return ["update_detection"]

    def get_deps(self):
        return {
            'interfaces': [
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
                ('paperwork_config', ['paperwork_backend.config.file',]),
            ]
        }

    def _register_config(self, core):
        setting = self.core.call_success(
            "paperwork_config_build_simple", "update",
            "enabled", lambda: False
        )
        self.core.call_all(
            "paperwork_config_register", "check_for_update", setting
        )
        setting = self.core.call_success(
            "paperwork_config_build_simple", "update",
            "last_update_found", lambda: _version.version
        )
        self.core.call_all(
            "paperwork_config_register", "last_update_found", setting
        )

    def _parse_version(self, version):
        version = version.split("-", 1)
        return tuple([int(x) for x in version[0].split(".")])

    def update_check(self):
        LOGGER.info("Looking for updates...")

        def on_success(update_data, core):
            latest_version = update_data['paperwork'][os.name]
            LOGGER.info("Version advertised: %s", latest_version)
            self.core.call_all(
                "paperwork_config_put", "last_update_found", latest_version
            )
            self.core.call_all("paperwork_config_save")
            self.update_compare()

        promise = openpaperwork_core.promise.Promise(self.core, lambda: "")
        promise = promise.then(self.http.get_request_promise(self.core))
        promise = promise.then(on_success, self.core)
        promise.schedule()

    def update_compare(self):
        remote_version = self.core.call_success(
            "paperwork_config_get", "last_update_found"
        )
        remote_version = self._parse_version(remote_version)
        LOGGER.info("Remote version: %s", remote_version)
        local_version = self._parse_version(_version.version)
        LOGGER.info("Current version: %s", local_version)
        if remote_version > local_version:
            self.core.call_all(
                "on_update_detected", local_version, remote_version
            )

    def init(self, core):
        super().init(core)
        self._register_config(core)
        self.periodic.register_config(core)
        self.http.register_config(core)

        if self.core.call_success("paperwork_config_get", "check_for_update"):
            self.periodic.do(core)
