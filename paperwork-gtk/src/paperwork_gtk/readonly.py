import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    # we want to be called last for sync()
    PRIORITY = -10000000

    def __init__(self):
        super().__init__()
        self.edit_enabled = False

    def get_interfaces(self):
        return [
            'backend_readonly',
            'syncable',
        ]

    def doc_transaction_start(self, out: list, total_expected=-1):
        # we don't care about document modifications
        pass

    def sync(self, promises: list):
        # due to sqlite limitations (no multiple transactions), we must
        # prevent the user from modifying documents while the sync is running
        LOGGER.info(
            "Switching to readonly mode (nb syncable: %d)",
            len(promises)
        )
        self.core.call_all("on_backend_readonly")

        def switch_readwrite():
            LOGGER.info("Switching to readwrite mode")
            self.core.call_all("on_backend_readwrite")

        promises.append(openpaperwork_core.promise.Promise(
            self.core, switch_readwrite
        ))
