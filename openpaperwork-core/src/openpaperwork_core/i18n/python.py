import datetime

from .. import (_, PluginBase)


class Plugin(PluginBase):
    def __init__(self):
        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)

        # Need the l10n plugin to be loaded first before getting the
        # translations
        self.i18n_today = None
        self.i18n_yesterday = None
        self.i18n_sizes = ()

    def get_interfaces(self):
        return ['i18n']

    def get_deps(self):
        return [
            {
                'interface': 'l10n',
                'defaults': ['openpaperwork_core.l10n.python'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.i18n_today = _("Today")
        self.i18n_yesterday = _("Yesterday")
        self.i18n_sizes = (
            _('%3.1f bytes'),
            _('%3.1f KiB'),
            _('%3.1f MiB'),
            _('%3.1f GiB'),
            _('%3.1f TiB'),
        )

    def i18n_date_short(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        if date == self.today:
            return self.i18n_today
        elif date == self.yesterday:
            return self.i18n_yesterday
        else:
            return date.strftime("%x")

    def i18n_parse_date_short(self, txt):
        if txt == self.i18n_today:
            return self.today
        elif txt == self.i18n_yesterday:
            return self.yesterday
        else:
            try:
                return datetime.datetime.strptime(txt, "%x").date()
            except ValueError:
                return None

    def i18n_date_long_year(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%Y")

    def i18n_date_long_month(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%B")

    def i18n_file_size(self, num):
        for string in self.i18n_sizes:
            if num < 1024.0:
                return string % (num)
            num /= 1024.0
        return self.i18n_sizes[-1] % (num)
