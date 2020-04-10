import sys

from . import PluginBase


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.original_hook = sys.excepthook

    def get_interfaces(self):
        return ['uncaught_exception']

    def get_deps(self):
        return [
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
        ]

    def init(self, core):
        super().init(core)
        sys.excepthook = self._on_uncaught_exception

    def _on_uncaught_exception(self, exc_type, exc_value, exc_tb):
        exc_info = (exc_type, exc_value, exc_tb)
        self.core.call_success(
            "mainloop_schedule", self._broadcast_exception, exc_info
        )

    def _broadcast_exception(self, exc_info):
        # make sure we don't loop
        sys.excepthook = self.original_hook
        try:
            nb = self.core.call_all("on_uncaught_exception", exc_info)
            if nb <= 0:
                # no log handler yet --> switch back to default
                self.original_hook(*exc_info)
        finally:
            sys.excepthook = self._on_uncaught_exception
