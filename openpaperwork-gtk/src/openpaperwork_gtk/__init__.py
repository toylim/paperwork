import gettext


def _(s):
    return gettext.dgettext('openpaperwork_gtk', s)


CLI_PLUGINS = [
    # plugins that can make sense to use even in the CLI application
    'openpaperwork_gtk.external_apps.gio',
    'openpaperwork_gtk.fs.gio',
    'openpaperwork_gtk.l10n',
]

GUI_PLUGINS = [
    'openpaperwork_gtk.bug_report',
    'openpaperwork_gtk.bug_report.http',
    'openpaperwork_gtk.bug_report.zip',
    'openpaperwork_gtk.colors',
    'openpaperwork_gtk.pixbuf.pillow',
    'openpaperwork_gtk.resources',
    'openpaperwork_gtk.screenshots',
    'openpaperwork_gtk.widgets.progress',
]
