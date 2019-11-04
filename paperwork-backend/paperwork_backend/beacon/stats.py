import datetime
import logging
import uuid

import openpaperwork_core

from . import (
    OpenpaperHttp,
    PeriodicTask
)
from .. import _version


LOGGER = logging.getLogger(__name__)

POST_STATS_SERVER = ("https", "openpaper.work")
POST_STATS_INTERVAL = datetime.timedelta(days=7)
POST_STATS_PATH = "/beacon/post_statistics"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.periodic = PeriodicTask(
            "statistics",
            datetime.timedelta(days=7),
            self.stats_send
        )
        self.http = OpenpaperHttp(
            "statistics", "https", "openpaper.work", "/beacon/post_statistics"
        )

    def get_interfaces(self):
        return [
            "stats_post",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
                ('paperwork_config', ['paperwork_backend.config.file',]),
            ]
        }

    def init(self, core):
        super().init(core)
        self._register_config(core)
        self.periodic.register_config(core)
        self.http.register_config(core)

        if self.core.call_success("paperwork_config_get", "send_statistics"):
            self.periodic.do(core)

    def _register_config(self, core):
        setting = self.core.call_success(
            "paperwork_config_build_simple", "statistics",
            "enabled", lambda: False
        )
        self.core.call_all(
            "paperwork_config_register", "send_statistics", setting
        )
        setting = self.core.call_success(
            "paperwork_config_build_simple", "statistics",
            "uuid", lambda: uuid.getnode()
        )
        self.core.call_all("paperwork_config_register", "uuid", setting)

    def _collect_stats(self, node_uuid):
        stats = {
            'uuid': node_uuid,
            'paperwork_version': _version.version,
            'nb_documents': 0,
            'os_name': '',
            'platform_architecture': '',
            'platform_processor': '',
            'platform_distribution': '',
            'cpu_count': 0,
        }
        self.core.call_all("stats_get", stats)
        return {'statistics': stats}

    def stats_send(self):
        node_uuid = self.core.call_success("paperwork_config_get", "uuid")
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._collect_stats, args=(node_uuid,)
        )
        promise = promise.then(
            self.http.get_request_promise(self.core)
        )

        def on_request_done():
            LOGGER.info("Statistics posted")
            self.core.call_all('on_stats_sent')

        promise = promise.then(on_request_done)
        promise.schedule()
