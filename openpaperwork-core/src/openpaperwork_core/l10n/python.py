import gettext
import locale
import logging

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    LANGS = (
        'es',
        'fr',
        'uk',
    )

    def get_interfaces(self):
        return [
            'l10n',
            'l10n_init',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'resources',
                'defaults': ['openpaperwork_core.resources.setuptools'],
            },
        ]

    def init(self, core):
        super().init(core)
        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            # happens e.g. when LC_ALL is set to a nonexisting locale
            LOGGER.warning(
                "Failed to set localization. Localization will be disabled"
            )
            return
        self.l10n_load('openpaperwork_core.l10n', 'openpaperwork_core')

    def l10n_load(self, python_package, text_domain, langs=None):
        if langs is None:
            langs = self.LANGS

        path = self.core.call_success(
            "resources_get_dir", python_package, 'out'
        )
        assert(path is not None)
        path = self.core.call_success("fs_unsafe", path)

        mo_file = gettext.find(text_domain, path)
        if mo_file is None:
            # expected if we don't have translation for the user language
            LOGGER.info("Failed to find valid locale for '%s'", text_domain)
            return

        LOGGER.info("Using locales in '%s'", path)
        for module in (gettext, locale):
            if hasattr(module, 'bindtextdomain'):
                module.bindtextdomain(text_domain, path)
            if hasattr(module, 'textdomain'):
                module.textdomain(text_domain)
