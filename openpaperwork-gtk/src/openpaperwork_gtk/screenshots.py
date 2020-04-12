import logging
import gettext

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    CAIRO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext
SCREENSHOT_DATE_FORMAT = "%Y%m%d_%H%M_%S"
MAX_DAYS = 31


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.windows = []
        self.archiver = None

    def get_interfaces(self):
        return [
            'bug_report_attachments',
            'chkdeps',
            'gtk_window_listener',
            'uncaught_exception_listener',
            'screenshot',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'file_archives',
                'defaults': ['openpaperwork_core.archives'],
            },
            {
                'interface': 'fs',
                'defaults': [
                    'openpaperwork_core.fs.memory',
                    'openpaperwork_core.fs.python',
                ],
            },
            {
                'interface': 'uncaught_exception',
                'defaults': ['openpaperwork_core.uncaught_exception'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.archiver = self.core.call_success(
            "file_archive_get", storage_name="screenshots",
            file_extension="png"
        )

    def chkdeps(self, out: dict):
        out['cairo'] = openpaperwork_core.deps.CAIRO

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def _snap_screenshot(self, fd):
        image_size = (0, 0)

        for window in self.windows:
            if not window.is_drawable():
                LOGGER.warning("Window %s cannot be screenshoted", window)
            else:
                LOGGER.info("Screenshoting window %s", window)

        for window in self.windows:
            if not window.is_drawable():
                continue
            alloc = window.get_allocation()
            image_size = (
                max(image_size[0], alloc.width),
                image_size[1] + alloc.height
            )

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, *image_size)
        cairo_ctx = cairo.Context(surface)

        for window in self.windows:
            if not window.is_drawable():
                continue
            alloc = window.get_allocation()
            window.draw(cairo_ctx)
            cairo_ctx.translate(0, alloc.height)

        surface.write_to_png(fd)

    def screenshot_snap_all_promise(self, temporary=True, name="screenshots"):
        if temporary:
            (file_url, fd) = self.core.call_success(
                "fs_mktemp", prefix="{}_".format(name), suffix=".png",
                mode="wb", on_disk=True
            )
        else:
            file_url = self.archiver.get_new(name=name)
            fd = self.core.call_success("fs_open", file_url, mode='wb')

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_screenshot_before",)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(
            self.core.call_success, "mainloop_execute",
            self._snap_screenshot, fd
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.catch(lambda *args, **kwargs: fd.close())
        promise = promise.then(fd.close)
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self.core.call_all, "on_screenshot_after")
        promise = promise.then(lambda *args, **kwargs: None)

        return (file_url, promise)

    def on_uncaught_exception(self, exc_info):
        LOGGER.info("Uncaught exception. Taking screenshots")
        (_, promise) = self.screenshot_snap_all_promise(
            name="uncaught_exception_screenshots"
        )
        promise.schedule()

    def bug_report_get_attachments(self, out: dict):
        for (date, file_path) in self.archiver.get_archived():
            file_url = "file://" + file_path
            out[file_url] = {
                'date': date,
                'include_by_default': False,
                'file_type': _("App. screenshots"),
                'file_url': file_url,
                'file_size': self.core.call_success("fs_getsize", file_url),
            }

        out['screenshot_now'] = {
            'include_by_default': False,
            'date': None,
            'file_type': _("App. screenshots"),
            'file_url': _("Select to generate"),
            'file_size': 0,
        }

    def _update_attachment(self, file_url, *args):
        self.core.call_all(
            "bug_report_update_attachment", "screenshot_now", {
                "file_url": file_url,
                "file_size": self.core.call_success("fs_getsize", file_url),
            }, *args
        )

    def on_bug_report_attachment_selected(self, attachment_id, *args):
        if attachment_id != 'screenshot_now':
            return
        (file_url, promise) = self.screenshot_snap_all_promise(temporary=True)
        promise = promise.then(self._update_attachment, file_url, *args)
        promise.schedule()
