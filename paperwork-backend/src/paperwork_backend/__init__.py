DEFAULT_CONFIG_PLUGINS = [
    'openpaperwork_core.config_file',
    'paperwork_backend.config.file'
]

DEFAULT_PLUGINS = [
    'openpaperwork_core.config_file',
    'paperwork_backend.docexport.img',
    'paperwork_backend.docexport.pdf',
    'paperwork_backend.docexport.pillowfight',
    'paperwork_backend.docimport.img',
    'paperwork_backend.docimport.pdf',
    'paperwork_backend.docscan.libinsane',
    'paperwork_backend.docscan.scan2doc',
    'paperwork_backend.doctracker',
    'paperwork_backend.fs.gio',
    'paperwork_backend.fs.memory',
    'paperwork_backend.guesswork.label.simplebayes',
    'paperwork_backend.guesswork.ocr.pyocr',
    'paperwork_backend.index.whoosh',
    'paperwork_backend.model.extra_text',
    'paperwork_backend.model.hocr',
    'paperwork_backend.model.img',
    'paperwork_backend.model.labels',
    'paperwork_backend.model.pdf',
    'paperwork_backend.model.workdir',
    'paperwork_backend.model.thumbnail',
    'paperwork_backend.pagetracker',
    'paperwork_backend.pillow.img',
    'paperwork_backend.pillow.pdf',
    'paperwork_backend.pyocr',
]

DEFAULT_GUI_PLUGINS = [
    'openpaperwork_core.log_collector',
    'paperwork_backend.beacon.stats',
    'paperwork_backend.beacon.sysinfo',
    'paperwork_backend.beacon.update',
] + DEFAULT_PLUGINS

DEFAULT_SHELL_PLUGINS = [
    'openpaperwork_core.log_print',
    "openpaperwork_core.mainloop_asyncio",
] + DEFAULT_PLUGINS
