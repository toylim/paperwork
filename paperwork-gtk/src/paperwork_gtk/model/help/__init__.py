import gettext

import openpaperwork_core


_ = gettext.gettext
HELP_FILES = (
    (_("Introduction"), "intro"),
    (_("User manual"), "usage"),
)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['help_files']

    def get_deps(self):
        return [
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def help_get_files(self):
        return HELP_FILES

    def help_get_file(self, name):
        # TODO(Jflesch): i18n
        return self.core.call_success(
            "resources_get_file", "paperwork_gtk.model.help.out", name + ".pdf"
        )
