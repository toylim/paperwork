import gettext


def _(s):
    return gettext.dgettext('paperwork_backend', s)


DEFAULT_CONFIG_PLUGINS = [
    'openpaperwork_core.archives',
    'openpaperwork_core.cmd.config',
    'openpaperwork_core.config',
    'openpaperwork_core.config.backend.configparser',
    'openpaperwork_core.logs.archives',
    'openpaperwork_core.logs.print',
    'openpaperwork_core.paths.xdg',
    'openpaperwork_core.uncaught_exception',
    'openpaperwork_gtk.fs.gio',
    'paperwork_backend.app',
]

DEFAULT_PLUGINS = [
    'openpaperwork_core.bug_report.censor',
    'openpaperwork_core.censor',
    'openpaperwork_core.cmd.chkdeps',
    'openpaperwork_core.display.print',
    'openpaperwork_core.external_apps.dbus',
    'openpaperwork_core.external_apps.windows',
    'openpaperwork_core.external_apps.xdg',
    'openpaperwork_core.flatpak',
    'openpaperwork_core.fs.memory',
    'openpaperwork_core.http',
    'openpaperwork_core.i18n.python',
    'openpaperwork_core.l10n.python',
    'openpaperwork_core.perfcheck.log',
    'openpaperwork_core.resources.setuptools',
    'openpaperwork_core.thread.pool',
    'openpaperwork_core.work_queue.default',
    'openpaperwork_gtk.external_apps.gio',
    'openpaperwork_gtk.fs.gio',
    'openpaperwork_gtk.l10n',
    'paperwork_backend.beacon.stats',
    'paperwork_backend.beacon.sysinfo',
    'paperwork_backend.beacon.update',
    'paperwork_backend.cairo.pillow',
    'paperwork_backend.cairo.poppler',
    'paperwork_backend.docexport.generic',
    'paperwork_backend.docexport.img',
    'paperwork_backend.docexport.pdf',
    'paperwork_backend.docexport.pillowfight',
    'paperwork_backend.docimport.img',
    'paperwork_backend.docimport.pdf',
    'paperwork_backend.docscan.libinsane',
    'paperwork_backend.docscan.scan2doc',
    'paperwork_backend.doctracker',
    # ACE is disabled by default: it's slow, and actually makes some scans
    # harder to read.
    # 'paperwork_backend.guesswork.color.libpillowfight',
    'paperwork_backend.guesswork.label.simplebayes',
    'paperwork_backend.guesswork.ocr.pyocr',
    'paperwork_backend.guesswork.orientation.pyocr',
    'paperwork_backend.i18n.pycountry',
    'paperwork_backend.i18n.scanner',
    'paperwork_backend.imgedit.color',
    'paperwork_backend.imgedit.crop',
    'paperwork_backend.imgedit.rotate',
    'paperwork_backend.index.whoosh',
    'paperwork_backend.model',
    'paperwork_backend.model.extra_text',
    'paperwork_backend.model.hocr',
    'paperwork_backend.model.img',
    'paperwork_backend.model.img_overlay',
    'paperwork_backend.model.labels',
    'paperwork_backend.model.pdf',
    'paperwork_backend.model.thumbnail',
    'paperwork_backend.model.workdir',
    'paperwork_backend.l10n',
    'paperwork_backend.pageedit.pageeditor',
    'paperwork_backend.pagetracker',
    'paperwork_backend.pillow.img',
    'paperwork_backend.pillow.pdf',
    'paperwork_backend.pillow.util',
    'paperwork_backend.pyocr',
    'paperwork_backend.sync',
]
