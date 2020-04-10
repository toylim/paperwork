import gettext
import logging

import openpaperwork_core


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return ['bug_report_method']

    def bug_report_complete(self, *args):
        self.core.call_all(
            "bug_report_add_method",
            _("Send automatically"),
            _("Send the bug report automatically to OpenPaper.work"),
            self._enable_http, self._disable_http,
            lambda *args, **kwargs: None,
            *args
        )

    def _enable_http(self, bug_report_widget_tree):
        pass

    def _disable_http(self, bug_report_widget_tree):
        pass
