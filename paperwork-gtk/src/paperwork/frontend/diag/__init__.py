import distro
import logging
import multiprocessing
import os
import platform
import pyocr
import sys

import gettext
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Libinsane

from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.jobs import Job, JobFactory


_ = gettext.gettext
logger = logging.getLogger(__name__)


class JobInfoGetter(Job):
    __gsignals__ = {
        'scan-progression': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_STRING,  # step
                              GObject.TYPE_FLOAT,  # [0.0-1.0]
                              )),
        'scan-done': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    STEP_SYSINFO = "a"
    STEP_PAPERWORK = "b"
    STEP_SCANNER = "c"
    STEP_PYOCR = "d"

    can_stop = True
    priority = 1000

    def __init__(self, factory, id, main_win, libinsane):
        super(JobInfoGetter, self).__init__(factory, id)
        self.main_win = main_win
        self.libinsane = libinsane
        # update translations
        JobInfoGetter.STEP_SYSINFO = _("system's information")
        JobInfoGetter.STEP_PAPERWORK = _("document statistics")
        JobInfoGetter.STEP_SCANNER = _("scanner's information")
        JobInfoGetter.STEP_PYOCR = _("Pyocr's information")

    def _get_sysinfo(self):
        self.emit('scan-progression', self.STEP_SYSINFO, 0.0)
        logger.info("====== START OF SYSTEM INFO ======")
        logger.info("os.name: {}".format(os.name))
        logger.info("sys.version: {}".format(sys.version))
        if hasattr(os, 'uname'):
            try:
                logger.info("os.uname: {}".format(os.uname()))
            except Exception as exc:
                logger.info("os.uname: {}".format(str(exc)))
        try:
            logger.info("platform.architecture: {}".format(
                platform.architecture()
            ))
            logger.info("platform.platform: {}".format(platform.platform()))
            logger.info("platform.processor: {}".format(
                platform.processor())
            )
            logger.info("platform.version: {}".format(platform.version()))
            logger.info("distro.linux_distribution: {}".format(
                distro.linux_distribution(full_distribution_name=False)
            ))
            if hasattr(platform, 'win32_ver'):
                logger.info("platform.win32_ver: {}".format(
                    platform.win32_ver()
                ))
            logger.info("multiprocessing.cpu_count: {}".format(
                multiprocessing.cpu_count()
            ))
        except Exception as exc:
            logger.exception(exc)
        try:
            mem = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
            logger.info("Available memory: {}".format(mem))
        except Exception as exc:
            logger.exception(exc)
        logger.info("====== END OF SYSTEM INFO ======")

    def _get_paperwork_info(self):
        self.emit('scan-progression', self.STEP_PAPERWORK, 0.0)
        logger.info("====== START OF PAPERWORK INFO ======")
        logger.info("Paperwork version: {}".format(self.main_win.version))
        logger.info("Scan library: Libinsane {}".format(
            Libinsane.Api.get_version())
        )

        nb_docs = 0
        nb_pages = 0
        max_pages = 0
        doc_types = {}

        docs = self.main_win.docsearch.docs
        nb_docs = len(docs)
        doc_idx = 0
        for doc in docs:
            if doc_idx % 10 == 0:
                self.emit(
                    'scan-progression', self.STEP_PAPERWORK, doc_idx / nb_docs
                )

            doc_type = str(type(doc))
            if doc_type not in doc_types:
                doc_types[doc_type] = 0
            else:
                doc_types[doc_type] += 1

            try:
                max_pages = max(max_pages, doc.nb_pages)
                doc_idx += 1
            except Exception as exc:
                logger.error(
                    "Exception while examining document {}".format(doc.docid),
                    exc_info=exc
                )

        logger.info("Total number of documents: {}".format(nb_docs))
        logger.info("Document types: {}".format(str(doc_types)))
        logger.info("Total number of pages: {} (average: {}/doc)".format(
            nb_pages, nb_pages / (nb_docs if nb_docs else -1)
        ))
        logger.info("Maximum number of pages in one document: {}".format(
            max_pages
        ))
        logger.info("====== END OF PAPERWORK INFO ======")

    def _get_scanner_info(self):
        self.emit('scan-progression', self.STEP_SCANNER, 0.0)
        logger.info("====== START OF SCANNER INFO ======")
        devices = self.libinsane.list_devices(
            Libinsane.DeviceLocations.ANY
        )
        logger.info("{} scanners found".format(len(devices)))

        for device_desc in devices:
            logger.info("=== %s ===", device_desc.get_dev_id())
            try:
                device = self.libinsane.get_device(device_desc.get_dev_id())
            except Exception as exc:
                logger.error(
                    "Failed to open device %s", device_desc.get_dev_id(),
                    exc_info=exc
                )
                continue

            for source in device.get_children():
                logger.info(
                    "=== %s/%s ===", device_desc.get_dev_id(),
                    source.get_name()
                )

                for opt in source.get_options():
                    logger.info("Option: {}".format(opt.get_name()))
                    logger.info("  Title: {}".format(opt.get_title()))
                    logger.info("  Desc: {}".format(opt.get_desc()))
                    logger.info("  Type: {}".format(str(opt.get_value_type())))
                    logger.info("  Unit: {}".format(str(opt.get_value_unit())))
                    logger.info("  Is readable ? {}".format(
                        str(opt.is_readable()))
                    )
                    logger.info("  Is writable ? {}".format(
                        str(opt.is_writable()))
                    )
                    logger.info("  Capabilities: {}".format(
                        str(opt.get_capabilities()))
                    )
                    logger.info("  Constraint type: {}".format(
                        str(opt.get_constraint_type()))
                    )
                    logger.info("  Constraint: {}".format(
                        str(opt.get_constraint()))
                    )
                    if opt.is_readable():
                        logger.info("  Value: {}".format(str(opt.get_value())))

        logger.info("====== END OF SCANNER INFORMATIONS ======")

    def _get_pyocr_info(self):
        self.emit('scan-progression', self.STEP_PYOCR, 0.0)
        logger.info("====== START OF PYOCR INFO ======")
        logger.info("Pyocr version: %s", str(pyocr.VERSION))
        for tool in pyocr.get_available_tools():
            logger.info("Tool: %s", str(tool.get_name()))
            logger.info("  Version: %s", str(tool.get_version()))
            logger.info(
                "  Can detect orientation: %s",
                str(tool.can_detect_orientation())
            )
        logger.info("====== END OF PYOCR INFORMATIONS ======")
        self.emit('scan-progression', self.STEP_PYOCR, 1.0)

    def do(self):
        # Simply log everything
        self.can_run = True
        try:
            self._get_sysinfo()
            if not self.can_run:
                return
            self._get_paperwork_info()
            if not self.can_run:
                return
            self._get_scanner_info()
            self._get_pyocr_info()
        except Exception as exc:
            logger.exception(exc)
        finally:
            self.emit('scan-done')

    def stop(self, will_resume=False):
        logger.info("InfoGetter interrupted")
        self.can_run = False


GObject.type_register(JobInfoGetter)


class JobFactoryInfoGetter(JobFactory):

    def __init__(self, diag_win, main_win, libinsane):
        super(JobFactoryInfoGetter, self).__init__("InfoGetter")
        self.diag_win = diag_win
        self.main_win = main_win
        self.libinsane = libinsane

    def make(self):
        job = JobInfoGetter(
            self, next(self.id_generator), self.main_win, self.libinsane
        )
        job.connect(
            'scan-progression',
            lambda job, step, progression: GLib.idle_add(
                self.diag_win.on_scan_progression_cb, step, progression
            )
        )
        job.connect(
            'scan-done',
            lambda job: GLib.idle_add(
                self.diag_win.on_scan_done_cb
            )
        )
        return job


class LogTracker(logging.Handler):
    # Assuming 1KB per line, it makes about 50MB of RAM
    # (+ memory allocator overhead)
    MAX_LINES = 50 * 1000
    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def __init__(self):
        super(LogTracker, self).__init__()
        self._formatter = logging.Formatter(
            '%(levelname)-6s %(name)-30s %(message)s'
        )
        self.output = []

    def emit(self, record):
        line = self._formatter.format(record)
        self.output.append(line)
        if len(self.output) > self.MAX_LINES:
            self.output.pop(0)

    def get_logs(self):
        return "\n".join(self.output)

    def on_uncatched_exception_cb(self, exc_type, exc_value, exc_tb):
        logger.error(
            "=== UNCATCHED EXCEPTION ===",
            exc_info=(exc_type, exc_value, exc_tb)
        )
        logger.error(
            "==========================="
        )

    @staticmethod
    def init():
        logger = logging.getLogger()
        handler = logging.StreamHandler()
        handler.setFormatter(g_log_tracker._formatter)
        logger.addHandler(handler)
        logger.addHandler(g_log_tracker)
        sys.excepthook = g_log_tracker.on_uncatched_exception_cb


g_log_tracker = LogTracker()


class DiagDialog(object):
    def __init__(self, main_win, libinsane):
        widget_tree = load_uifile(
            os.path.join("diag", "diagdialog.glade"))

        self.buf = widget_tree.get_object("textbufferDiag")

        self.dialog = widget_tree.get_object("dialogDiag")
        self.dialog.set_transient_for(main_win.window)
        self.dialog.connect("response", self.on_response_cb)

        self.progressbar = widget_tree.get_object("progressbarDiag")

        self.scrollwin = widget_tree.get_object("scrolledwindowDiag")

        self._main_win = main_win

        self.set_text(_("Please wait. It may take a few minutes ..."))

        txt_view = widget_tree.get_object("textviewDiag")
        txt_view.connect("size-allocate", self.scroll_to_bottom)

        self.scheduler = main_win.schedulers['main']
        self.factory = JobFactoryInfoGetter(self, main_win, libinsane)
        job = self.factory.make()
        self.scheduler.schedule(job)

        self.dialog.connect("destroy", self.on_destroy_cb)

    def set_text(self, txt):
        self.buf.set_text(txt, -1)
        GLib.idle_add(self.scroll_to_bottom)

    def scroll_to_bottom(self, *args, **kwargs):
        vadj = self.scrollwin.get_vadjustment()
        if vadj is None:  # dialog has been closed
            return
        vadj.set_value(vadj.get_upper())

    def on_scan_progression_cb(self, step, progression):
        self.progressbar.set_text(_("Getting {} ({}%)").format(
            step, int(progression * 100))
        )
        self.progressbar.set_fraction(progression)

    def on_scan_done_cb(self):
        self.set_text(g_log_tracker.get_logs())
        self.progressbar.set_text(_("Diagnostic information are ready"))
        self.progressbar.set_fraction(1.0)

    def on_response_cb(self, widget, response):
        if response == 0:  # close
            self.dialog.set_visible(False)
            self.dialog.destroy()
            self.dialog = None
            return True
        if response == 1:  # save as
            chooser = Gtk.FileChooserDialog(
                title=_("Save as"),
                transient_for=self._main_win.window,
                action=Gtk.FileChooserAction.SAVE
            )
            file_filter = Gtk.FileFilter()
            file_filter.set_name("text")
            file_filter.add_mime_type("text/plain")
            chooser.add_filter(file_filter)
            chooser.add_buttons(Gtk.STOCK_CANCEL,
                                Gtk.ResponseType.CANCEL,
                                Gtk.STOCK_SAVE,
                                Gtk.ResponseType.OK)
            response = chooser.run()
            try:
                if response != Gtk.ResponseType.OK:
                    return True

                filepath = chooser.get_filename()
                with open(filepath, "w") as fd:
                    start = self.buf.get_iter_at_offset(0)
                    end = self.buf.get_iter_at_offset(-1)
                    text = self.buf.get_text(start, end, False)
                    fd.write(text)
            finally:
                chooser.set_visible(False)
                chooser.destroy()

            return True
        if response == 2:  # copy
            gdk_win = self._main_win.window.get_window()
            clipboard = Gtk.Clipboard.get_default(gdk_win.get_display())
            start = self.buf.get_iter_at_offset(0)
            end = self.buf.get_iter_at_offset(-1)
            text = self.buf.get_text(start, end, False)
            clipboard.set_text(text, -1)
            return True

    def on_destroy_cb(self, _):
        self.scheduler.cancel_all(self.factory)

    def show(self):
        self.dialog.set_visible(True)
