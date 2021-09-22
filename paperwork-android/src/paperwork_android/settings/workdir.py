import logging

import android.permissions
import android.storage
import kivymd.uix.filemanager

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def __init__(self):
        super().__init__()
        self.file_manager = None

    def get_interfaces(self):
        return ['setting']

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
                'interface': 'settings_window',
                'defaults': ['paperwork_android.settings'],
            },
        ]

    def _select_work_directory(self, *args, **kwargs):
        if android.permissions.check_permission(
                    android.permissions.Permission.READ_EXTERNAL_STORAGE
                ):
            self.__select_work_directory()
        else:
            android.permissions.request_permissions([
                android.permissions.Permission.READ_EXTERNAL_STORAGE
            ], callback=self.__select_work_directory)

    def __select_work_directory(self, *args, **kwargs):
        workdir = self.core.call_success("config_get", "workdir")
        workdir = self.core.call_success("fs_unsafe", workdir)
        ext_storage = android.storage.primary_external_storage_path()

        path = workdir
        if not path.startswith(ext_storage):
            path = None

        self.file_manager = kivymd.uix.filemanager.MDFileManager(
            exit_manager=self.exit_manager,
            select_path=self.select_path,
            selector='folder',
            search='dirs',
        )
        if path is not None:
            self.file_manager.show(path)
        elif hasattr(self.file_manager, 'show_disks'):
            self.file_manager.show_disks()
        else:
            self.file_manager.show(ext_storage)

    def select_path(self, path):
        path = self.core.call_success("fs_safe", path)
        LOGGER.info("Selected work directory: %s", path)
        self.core.call_all("config_put", "workdir", path)
        self.exit_manager()

    def exit_manager(self, *args, **kwargs):
        self.file_manager.close()
        self.file_manager = None

    def settings_get(self, settings: dict):
        settings.append(
            (
                self._select_work_directory,
                "Work directory",
                "Directory where all your documents are stored"
            )
        )

    def on_back_key(self):
        if self.file_manager is None:
            return None
        self.file_manager.back()
        return True
