import datetime

from .. import (_, PluginBase)


TODAY = _("Today")
YESTERDAY = _("Yesterday")
_SIZE_FMT_STRINGS = (
    _('%3.1f bytes'),
    _('%3.1f KiB'),
    _('%3.1f MiB'),
    _('%3.1f GiB'),
    _('%3.1f TiB'),
)


class Plugin(PluginBase):
    def __init__(self):
        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)

    def get_interfaces(self):
        return ['i18n']

    def i18n_date_short(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        if date == self.today:
            return TODAY
        elif date == self.yesterday:
            return YESTERDAY
        else:
            return date.strftime("%x")

    def i18n_parse_date_short(self, txt):
        if txt == TODAY:
            return self.today
        elif txt == YESTERDAY:
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
        for string in _SIZE_FMT_STRINGS:
            if num < 1024.0:
                return string % (num)
            num /= 1024.0
        return _SIZE_FMT_STRINGS[-1] % (num)
