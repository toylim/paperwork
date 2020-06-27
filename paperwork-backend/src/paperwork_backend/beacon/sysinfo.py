import distro
import os
import platform

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def get_interfaces(self):
        return ['stats']

    def get_deps(self):
        return [
            {
                'interface': 'stats_post',
                'defaults': ['paperwork_backend.beacon.stats'],
            }
        ]

    def stats_get(self, out: dict):
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

        out['os_name'] = os_name
        out['platform_architecture'] = str(platform.architecture())
        out['platform_processor'] = processor
        out['platform_distribution'] = distribution
        out['cpu_count'] = os.cpu_count()
        return out
