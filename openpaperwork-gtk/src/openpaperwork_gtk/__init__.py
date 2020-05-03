import gettext


def _(s):
    return gettext.dgettext('openpaperwork_gtk', s)
