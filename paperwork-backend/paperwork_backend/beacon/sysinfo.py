import distro
import os
import platform

import openpaperwork_core


class Plugin(openpaperwork_base.PluginBase):
    def get_deps(self):
        return {
            'interfaces': [
                ("stats_post", ['paperwork_backend.beacon.stats',]),
            ]
        }

    def stats_get(self, out: dict):
        flatpak = os.path.exists("/app")

        if os.name == 'nt':
            distribution = str(platform.win32_ver())
        else:
            distribution = str(distro.linux_distribution(
                full_distribution_name=False
            ))
        processor = ""
        os_name = os.name
        if os_name != 'nt':  # processor contains too much infos on Windows
            processor = str(platform.processor())
            if flatpak:
                os_name += " (flatpak)"

        out['os_name'] = os_name
        out['platform_architecture'] = str(platform.architecture())
        out['platform_processor'] = processor
        out['platform_distribution'] = distribution
        out['cpu_count'] = os.cpu_count()
