import datetime
import gettext

from .. import PluginBase


_ = gettext.gettext

TODAY = _("Today")
YESTERDAY = _("Yesterday")


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
            return datetime.datetime.strptime(txt, "%x").date()

    def i18n_date_long_year(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%Y")

    def i18n_date_long_month(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%B")
