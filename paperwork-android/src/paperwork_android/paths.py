import android.storage

from openpaperwork_core import PluginBase


class Plugin(PluginBase):
    def get_interfaces(self):
        return [
            'data_dir_handler',
            'paths',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app',
                'defaults': ['openpaperwork_core.app'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python']
            },
        ]

    def paths_get_config_dir(self):
        storage = self.core.call_success(
            "fs_safe", android.storage.app_storage_path()
        )
        r = self.core.call_success("fs_join", storage, "config")
        self.core.call_success("fs_mkdir_p", r)
        return r

    def paths_get_data_dir(self):
        storage = self.core.call_success(
            "fs_safe", android.storage.app_storage_path()
        )
        r = self.core.call_success("fs_join", storage, "data")
        self.core.call_success("fs_mkdir_p", r)
        return r

    def data_dir_handler_get_individual_data_dir(self):
        r = self.core.call_success(
            "fs_join", self.paths_get_data_dir(), "workdir_data"
        )
        self.core.call_success("fs_mkdir_p", r)
        return r
