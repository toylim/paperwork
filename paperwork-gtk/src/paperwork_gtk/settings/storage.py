import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000000

    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return [
            'gtk_settings',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.workdir = self.core.call_success("config_get", "workdir")

    def complete_settings_dialog(self, settings_box):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings", "storage.glade"
        )

        workdir_chooser = widget_tree.get_object("work_dir_chooser")
        workdir_chooser.set_uri(self.workdir)
        workdir_chooser.connect("file-set", self._on_file_set)

        self.core.call_success(
            "add_setting_to_dialog", settings_box, _("Storage"),
            [widget_tree.get_object("workdir")]
        )

    def _on_file_set(self, file_chooser):
        workdir = file_chooser.get_uri()
        LOGGER.info("Setting work directory to %s", workdir)
        self.core.call_all("config_put", "workdir", workdir)

    def config_save(self):
        workdir = self.core.call_success("config_get", "workdir")

        if workdir != self.workdir:
            LOGGER.info("Work directory has been changed --> Synchronizing")
            promises = []
            self.core.call_all("sync", promises)
            promise = promises[0]
            for p in promises[1:]:
                promise = promise.then(p)
            promise.schedule()

        self.workdir = workdir
