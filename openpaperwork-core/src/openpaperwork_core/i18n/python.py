import datetime
import gettext

from .. import PluginBase


_ = gettext.gettext


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
            return _("Today")
        elif date == self.yesterday:
            return _("Yesterday")
        else:
            return date.strftime("%x")

    def i18n_date_long_year(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%Y")

    def i18n_date_long_month(self, date):
        if hasattr(date, 'date'):
            date = date.date()  # datetime --> date
        return date.strftime("%B")
