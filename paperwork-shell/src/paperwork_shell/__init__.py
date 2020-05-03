import gettext


def _(s):
    return gettext.dgettext('paperwork_shell', s)
