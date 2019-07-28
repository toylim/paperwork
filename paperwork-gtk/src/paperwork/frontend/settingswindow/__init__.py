#   Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.
"""
Settings window.
"""

import os
import time

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Libinsane
import gettext
import logging
import PIL.Image
import pycountry
import pyocr

from paperwork_backend.util import find_language

from paperwork.frontend.util import load_uifile
from paperwork.frontend.util.actions import SimpleAction
from paperwork.frontend.util.canvas import Canvas
from paperwork.frontend.util.canvas.animations import ScanAnimation
from paperwork.frontend.util.canvas.drawers import PillowImageDrawer
from paperwork.frontend.util.img import raw2pixbuf
from paperwork.frontend.util.imgcutting import ImgGripHandler
from paperwork.frontend.util.jobs import Job, JobFactory, JobScheduler
from paperwork.frontend.util.jobs import JobFactoryProgressUpdater


_ = gettext.gettext
logger = logging.getLogger(__name__)


DEFAULT_CALIBRATION_RESOLUTION = 200


class JobDeviceFinder(Job):
    __gsignals__ = {
        'device-finding-start': (GObject.SignalFlags.RUN_LAST, None,
                                 ()),
        'device-found': (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_STRING,  # user name
                          GObject.TYPE_STRING,  # device id
                          GObject.TYPE_BOOLEAN)),  # is the active one
        'device-finding-end': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    can_stop = False
    priority = 500

    def __init__(self, factory, id, libinsane, selected_devid):
        Job.__init__(self, factory, id)
        self.libinsane = libinsane
        self.__selected_devid = selected_devid

    @staticmethod
    def __get_dev_name(dev):
        """
        Return the human representation of a device

        Returns:
            A string
        """
        return ("%s %s" % (dev.get_dev_vendor(), dev.get_dev_model()))

    def do(self):
        self.emit("device-finding-start")
        self._wait(2.0)
        try:
            logger.info("Looking for scan devices ...")
            devices = self.libinsane.list_devices(
                Libinsane.DeviceLocations.ANY
            )
            for device in devices:
                selected = (self.__selected_devid == device.get_dev_id())
                name = self.__get_dev_name(device)
                logger.info("Device found: [%s] -> [%s]" % (
                    name, device.get_dev_id())
                )
                self.emit('device-found', name, device.get_dev_id(), selected)
            logger.info("End of scan for device")
        finally:
            self.emit("device-finding-end")


GObject.type_register(JobDeviceFinder)


class JobFactoryDeviceFinder(JobFactory):

    def __init__(self, settings_win, libinsane, selected_devid):
        JobFactory.__init__(self, "DeviceFinder")
        self.libinsane = libinsane
        self.__selected_devid = selected_devid
        self.__settings_win = settings_win

    def make(self):
        job = JobDeviceFinder(
            self, next(self.id_generator),
            self.libinsane, self.__selected_devid
        )
        job.connect('device-finding-start',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_device_finding_start_cb))
        job.connect('device-found',
                    lambda job, user_name, store_name, active:
                    GLib.idle_add(self.__settings_win.on_value_found_cb,
                                  self.__settings_win.device_settings['devid'],
                                  user_name, store_name, active))
        job.connect('device-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['devid']))
        return job


class JobSourceFinder(Job):
    __gsignals__ = {
        'source-finding-start': (GObject.SignalFlags.RUN_LAST,
                                 None, ()),
        'source-found': (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_STRING,  # user name (translated)
                          GObject.TYPE_STRING,  # source name
                          GObject.TYPE_BOOLEAN, )),  # is the active one
        'source-finding-end': (GObject.SignalFlags.RUN_LAST,
                               None, ())
    }

    can_stop = False
    priority = 490
    TRANSLATIONS = {
        'auto': _("Automatic"),
        'flatbed': _("Flatbed"),
        'adf': _("Automatic Feeder"),
        'feeder': _("Automatic Feeder"),
    }

    def __init__(self, factory, id, libinsane, selected_source, devid):
        Job.__init__(self, factory, id)
        self.libinsane = libinsane
        self.__selected_source = selected_source
        self.__devid = devid

    def __get_source_name_translated(self, src_id):
        if src_id.lower() in self.TRANSLATIONS:
            return self.TRANSLATIONS[src_id.lower()]
        logger.warning("No translation for source [%s]" % src_id)
        return src_id

    def do(self):
        self.emit("source-finding-start")
        try:
            logger.info("Looking for sources of device [%s]"
                        % (self.__devid))
            device = self.libinsane.get_device(self.__devid)
            sources = [src.get_name() for src in device.get_children()]
            logger.info("Sources found: %s" % str(sources))
            for source in sources:
                name = self.__get_source_name_translated(source)
                self.emit('source-found', name, source,
                          (source == self.__selected_source))
            logger.info("Got all the sources")
        finally:
            self.emit("source-finding-end")


GObject.type_register(JobSourceFinder)


class JobFactorySourceFinder(JobFactory):

    def __init__(self, settings_win, libinsane, selected_source):
        JobFactory.__init__(self, "SourceFinder")
        self.libinsane = libinsane
        self.__settings_win = settings_win
        self.__selected_source = selected_source

    def make(self, devid):
        job = JobSourceFinder(self, next(self.id_generator),
                              self.libinsane, self.__selected_source, devid)
        job.connect('source-finding-start',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_start_cb,
                        self.__settings_win.device_settings['source']))
        job.connect('source-found',
                    lambda job, user_name, store_name, active:
                    GLib.idle_add(
                        self.__settings_win.on_value_found_cb,
                        self.__settings_win.device_settings['source'],
                        user_name, store_name, active))
        job.connect('source-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['source']))
        job.connect('source-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_source_finding_end_cb))
        return job


class JobResolutionFinder(Job):
    __gsignals__ = {
        'resolution-finding-start': (GObject.SignalFlags.RUN_LAST,
                                     None, ()),
        'resolution-found': (GObject.SignalFlags.RUN_LAST, None,
                             (GObject.TYPE_STRING,  # user name
                              GObject.TYPE_INT,  # resolution value
                              GObject.TYPE_BOOLEAN)),  # is the active one
        'resolution-finding-end': (GObject.SignalFlags.RUN_LAST,
                                   None, ())
    }

    can_stop = False
    priority = 490

    def __init__(self, factory, id,
                 core, libinsane,
                 selected_resolution,
                 devid, srcid):
        Job.__init__(self, factory, id)
        self.core = core
        self.libinsane = libinsane
        self.__selected_resolution = selected_resolution
        self.__devid = devid
        self.__srcid = srcid
        self.recommended = self.core.call_success(
            "paperwork_config_get_default", "scanner_resolution"
        )

    def __get_resolution_name(self, resolution):
        """
        Return the name corresponding to a resolution

        Arguments:
            resolution --- the resolution (integer)
        """
        txt = ("%d" % (resolution))
        if (resolution == self.recommended):
            txt += _(' (recommended)')
        return txt

    def do(self):
        self.emit("resolution-finding-start")
        try:
            logger.info(
                "Looking for resolution of device [%s]", self.__devid
            )
            device = self.libinsane.get_device(self.__devid)

            sources = device.get_children()
            sources = {src.get_name(): src for src in sources}
            src = sources[self.__srcid]

            opts = src.get_options()
            opts = {opt.get_name(): opt for opt in opts}

            if 'resolution' in opts:
                resolutions = opts['resolution'].get_constraint()
            else:
                resolutions = []
            if resolutions:
                logger.info("Resolutions found: %s" % str(resolutions))
            else:
                logger.warning(
                    "No possible resolutions specified. Assuming default"
                )
                resolutions = [75, 100, 150, 200, 300, 600, 1200]

            for resolution in resolutions:
                name = self.__get_resolution_name(resolution)
                self.emit('resolution-found', name, resolution,
                          (resolution == self.__selected_resolution))
            logger.info("Got all the resolutions")
        finally:
            self.emit("resolution-finding-end")


GObject.type_register(JobResolutionFinder)


class JobFactoryResolutionFinder(JobFactory):

    def __init__(self, core, settings_win, libinsane, selected_resolution):
        JobFactory.__init__(self, "ResolutionFinder")
        self.core = core
        self.__settings_win = settings_win
        self.libinsane = libinsane
        self.__selected_resolution = selected_resolution

    def make(self, devid, srcid):
        job = JobResolutionFinder(self, next(self.id_generator),
                                  self.core, self.libinsane,
                                  self.__selected_resolution,
                                  devid, srcid)
        job.connect('resolution-finding-start',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_start_cb,
                        self.__settings_win.device_settings['resolution']))
        job.connect('resolution-found',
                    lambda job, store_name, user_name, active:
                    GLib.idle_add(
                        self.__settings_win.on_value_found_cb,
                        self.__settings_win.device_settings['resolution'],
                        store_name, user_name, active))
        job.connect('resolution-finding-end',
                    lambda job: GLib.idle_add(
                        self.__settings_win.on_finding_end_cb,
                        self.__settings_win.device_settings['resolution']))
        return job


class JobCalibrationScan(Job):
    __gsignals__ = {
        'calibration-scan-start': (GObject.SignalFlags.RUN_LAST, None,
                                   ()),
        'calibration-scan-info': (GObject.SignalFlags.RUN_LAST, None,
                                  (
                                      # expected size
                                      GObject.TYPE_INT,
                                      GObject.TYPE_INT,
                                  )),
        'calibration-scan-img': (
            GObject.SignalFlags.RUN_LAST, None,
            (
                # line where to put the image
                GObject.TYPE_INT,
                GObject.TYPE_PYOBJECT,
            )
        ),
        'calibration-scan-done': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_PYOBJECT,  # Pillow image
                                   GObject.TYPE_INT, )),  # scan resolution
        'calibration-scan-error': (GObject.SignalFlags.RUN_LAST, None,
                                   (GObject.TYPE_STRING,)),  # error message
        'calibration-scan-canceled': (GObject.SignalFlags.RUN_LAST, None,
                                      ()),
    }

    can_stop = True
    priority = 495

    def __init__(
            self, factory, id, libinsane,
            resolutions_store, devid, source=None):
        Job.__init__(self, factory, id)
        self.libinsane = libinsane
        self.__resolutions_store = resolutions_store
        self.__devid = devid
        self.__source = source
        self.can_run = False

    def do(self):
        self.can_run = True
        self.emit('calibration-scan-start')

        try:
            (img, resolution) = self._do()
        except StopIteration:
            logger.warning("Calibration scan failed: No paper to scan")
            self.emit('calibration-scan-error',
                      _("No paper to scan"))
            raise
        except Exception as exc:
            logger.warning("Calibration scan failed: {}".format(str(exc)))
            self.emit('calibration-scan-error',
                      _("Error while scanning: {}".format(str(exc))))
            raise

        self.emit('calibration-scan-done', img, resolution)

    def _set_value(self, src, opt_name, opt_value):
        opts = src.get_options()
        opts = {opt.get_name(): opt for opt in opts}
        opts[opt_name].set_value(opt_value)
        logger.info(
            "%s->%s set to %s", src.get_name(), opt_name, str(opt_value)
        )

    def _do(self):
        # find the best resolution : the default calibration resolution
        # is not always available
        resolutions = [x[1] for x in self.__resolutions_store]
        resolutions.sort()

        resolution = DEFAULT_CALIBRATION_RESOLUTION
        for nresolution in resolutions:
            if nresolution > DEFAULT_CALIBRATION_RESOLUTION:
                break
            resolution = nresolution

        logger.info("Will do the calibration scan with a resolution of %d",
                    resolution)

        # scan
        dev = self.libinsane.get_device(self.__devid)
        sources = dev.get_children()
        sources = {source.get_name(): source for source in sources}

        if self.__source:
            source = sources[self.__source]
        else:
            source = dev
        logger.info("Scanner source set to '%s'", source.get_name())
        self._set_value(source, 'resolution', resolution)
        self._set_value(source, 'mode', 'Color')

        scan_session = source.scan_start()
        scan_parameters = scan_session.get_scan_parameters()
        self.emit(
            'calibration-scan-info',
            scan_parameters.get_width(), scan_parameters.get_height()
        )

        assert(scan_parameters.get_format() == Libinsane.ImgFormat.RAW_RGB_24)
        line_length = scan_parameters.get_width() * 3

        last_line = 0
        whole_image = bytearray()
        chunk = bytearray()
        while self.can_run and not scan_session.end_of_page():
            r = 0
            while r <= 128 * 1024 and not scan_session.end_of_page():
                out = scan_session.read_bytes(64 * 1024).get_data()
                r += len(out)
                chunk.extend(out)

            split = len(chunk) - (len(chunk) % line_length)
            next_chunk = chunk[split:]
            chunk = chunk[:split]

            whole_image.extend(chunk)
            pixbuf = raw2pixbuf(chunk, scan_parameters)
            if pixbuf is None:
                continue
            self.emit('calibration-scan-img', last_line, pixbuf)

            time.sleep(0)  # Give some CPU time to Gtk
            last_line += (split / line_length)
            chunk = next_chunk
        if not self.can_run:
            self.emit('calibration-scan-canceled')
            scan_session.scan.cancel()
            return

        image = PIL.Image.frombuffer(
            "RGB",
            (
                scan_parameters.get_width(),
                int(len(whole_image) / line_length)
            ),
            bytes(whole_image), "raw", "RGB", 0, 1
        )
        return (image, resolution)

    def stop(self, will_resume=False):
        assert(not will_resume)
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobCalibrationScan)


class JobFactoryCalibrationScan(JobFactory):

    def __init__(self, settings_win, libinsane, resolutions_store):
        JobFactory.__init__(self, "CalibrationScan")
        self.libinsane = libinsane
        self.__settings_win = settings_win
        self.__resolutions_store = resolutions_store

    def make(self, devid, source):
        job = JobCalibrationScan(self, next(self.id_generator),
                                 self.libinsane,
                                 self.__resolutions_store,
                                 devid, source)
        job.connect('calibration-scan-start',
                    lambda job:
                    GLib.idle_add(self.__settings_win.on_scan_start))
        job.connect('calibration-scan-info',
                    lambda job, size_x, size_y:
                    GLib.idle_add(self.__settings_win.on_scan_info,
                                  (size_x, size_y)))
        job.connect('calibration-scan-img',
                    lambda job, line, img:
                    GLib.idle_add(self.__settings_win.on_scan_img, line, img))
        job.connect('calibration-scan-error',
                    lambda job, error:
                    GLib.idle_add(self.__settings_win.on_scan_error, error))
        job.connect('calibration-scan-done',
                    lambda job, img, resolution:
                    GLib.idle_add(self.__settings_win.on_scan_done, img,
                                  resolution))
        job.connect('calibration-scan-canceled',
                    lambda job:
                    GLib.idle_add(self.__settings_win.on_scan_canceled))
        return job


class ActionSelectScanner(SimpleAction):
    enabled = True

    def __init__(self, settings_win, flatpak):
        super(ActionSelectScanner, self).__init__("New scanner selected")
        self.__settings_win = settings_win
        self.flatpak = flatpak

    def do(self):
        GLib.idle_add(self._do)

    def _do(self):
        self.__settings_win.update_active_settings()

        devid_settings = self.__settings_win.device_settings['devid']
        if len(devid_settings['stores']['loaded']) <= 0 and self.flatpak:
            widget_tree = load_uifile(
                os.path.join("settingswindow", "saned.glade")
            )
            dialog = widget_tree.get_object("sanedDialog")
            dialog.set_transient_for(self.__settings_win.window)
            dialog.set_modal(True)
            widget_tree.get_object("buttonOk").connect(
                "clicked", lambda button: dialog.destroy()
            )
            dialog.set_visible(True)

        dev_id = devid_settings['active_id']
        if dev_id == "":
            # happens when the scanner list has been updated
            # but no scanner has been found
            for setting in ['resolution', 'source']:
                settings = self.__settings_win.device_settings[setting]
                settings['stores']['loaded'].clear()
                settings['gui'].set_model(settings['stores']['loaded'])
                settings['gui'].set_sensitive(False)
            self.__settings_win.calibration["scan_button"].set_sensitive(False)
            return
        logger.info("Selected scanner: %s", dev_id)

        # no point in trying to stop the previous jobs, they are unstoppable
        job = self.__settings_win.job_factories['source_finder'].make(dev_id)
        self.__settings_win.schedulers['main'].schedule(job)


class ActionSelectSource(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        super(ActionSelectSource, self).__init__("New source selected")
        self.__settings_win = settings_win

    def do(self):
        self.__settings_win.update_active_settings()

        dev_id = self.__settings_win.device_settings['devid']['active_id']
        logger.info("Selected device: %s", dev_id)
        if dev_id == "":
            logger.warning("No device selected")
            return
        src_id = self.__settings_win.device_settings['source']['active_id']
        logger.info("Selected source: %s", src_id)
        if src_id == "":
            # happens when the scanner list has been updated
            # but no source has been found
            settings = self.__settings_win.device_settings['resolution']
            settings['stores']['loaded'].clear()
            settings['gui'].set_model(settings['stores']['loaded'])
            settings['gui'].set_sensitive(False)
            return
        self.__settings_win.calibration["scan_button"].set_sensitive(True)
        job = self.__settings_win.job_factories['resolution_finder'].make(
            dev_id, src_id
        )
        self.__settings_win.schedulers['main'].schedule(job)


class ActionToggleOCRState(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        super(ActionToggleOCRState, self).__init__("Toggle OCR state")
        self.__settings_win = settings_win

    def do(self):
        SimpleAction.do(self)
        self.__settings_win.set_ocr_opts_state()


class ActionApplySettings(SimpleAction):
    enabled = True

    def __init__(self, core, settings_win):
        super(ActionApplySettings, self).__init__("Apply settings")
        self.core = core
        self.__settings_win = settings_win

    def do(self):
        self.__settings_win.update_active_settings()

        need_reindex = False
        workdir = self.__settings_win.workdir_chooser.get_uri()
        current_workdir = self.core.call_success(
            "paperwork_config_get", "workdir"
        )
        if workdir != current_workdir:
            self.core.call_all("paperwork_config_put", 'workdir', workdir)
            need_reindex = True

        try:
            setting = self.__settings_win.device_settings['devid']
            if setting['active_id'] != "":
                self.core.call_all(
                    "paperwork_config_put", 'scanner_devid',
                    setting['active_id']
                )

            setting = self.__settings_win.device_settings['source']
            if setting['active_id'] != "":
                self.core.call_all(
                    "paperwork_config_put", 'scanner_source',
                    setting['active_id']
                )

            has_feeder = self.__settings_win.device_settings['has_feeder']
            self.core.call_all(
                "paperwork_config_put", 'scanner_has_feeder', has_feeder
            )

            setting = self.__settings_win.device_settings['resolution']
            if setting['active_id'] != "":
                self.core.call_all(
                    "paperwork_config_put", 'scanner_resolution',
                    setting['active_id']
                )
        except Exception as exc:
            logger.warning(
                "Failed to update scanner settings: %s", str(exc),
                exc_info=exc
            )

        setting = self.__settings_win.ocr_settings['enabled']
        enabled = setting['gui'].get_active()
        self.core.call_all('paperwork_config_put', 'ocr_enabled', enabled)

        setting = self.__settings_win.ocr_settings['lang']
        idx = setting['gui'].get_active()
        if idx >= 0:
            lang = setting['store'][idx][1]
            self.core.call_all('paperwork_config_put', 'ocr_lang', lang)

        update = self.__settings_win.network_settings['update'].get_active()
        self.core.call_all('paperwork_config_put', 'check_for_update', update)

        stats = self.__settings_win.network_settings['statistics'].get_active()
        self.core.call_all('paperwork_config_put', 'send_statistics', stats)

        if self.__settings_win.grips is not None:
            coords = self.__settings_win.grips.get_coords()
            self.core.call_all('paperwork_config_put', 'scanner_calibration',
                (self.__settings_win.calibration['resolution'], coords)
            )

        self.core.call_all("paperwork_config_save")

        self.__settings_win.hide()

        if need_reindex:
            self.__settings_win.emit("need-reindex")
        self.__settings_win.emit("config-changed")


class ActionScanCalibration(SimpleAction):
    enabled = True

    def __init__(self, settings_win):
        self.settings_win = settings_win
        super(ActionScanCalibration, self).__init__("Scan calibration sheet")

    def do(self):
        self.settings_win.update_active_settings()

        devid = self.settings_win.device_settings['devid']['active_id']
        source = self.settings_win.device_settings['source']['active_id']

        job = self.settings_win.job_factories['scan'].make(devid, source)
        self.settings_win.schedulers['main'].schedule(job)


class SettingsWindow(GObject.GObject):
    """
    Settings window.
    """

    __gsignals__ = {
        'need-reindex': (GObject.SignalFlags.RUN_LAST, None, ()),
        'config-changed': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(
            self, core, main_scheduler, mainwindow_gui, libinsane,
            flatpak):
        super(SettingsWindow, self).__init__()

        self.core = core
        self.schedulers = {
            'main': main_scheduler,
            'progress': JobScheduler('progress'),
        }
        self.local_schedulers = [
            self.schedulers['progress'],
        ]

        widget_tree = load_uifile(
            os.path.join("settingswindow", "settingswindow.glade"))
        # self.widget_tree is for tests/screenshots ONLY
        self.widget_tree = widget_tree

        self.window = widget_tree.get_object("windowSettings")
        self.window.set_transient_for(mainwindow_gui)

        self.workdir_chooser = widget_tree.get_object("filechooserbutton")

        self.network_settings = {
            "update": widget_tree.get_object("checkUpdate"),
            "statistics": widget_tree.get_object("checkStatistics")
        }

        self.ocr_settings = {
            "enabled": {
                'gui': widget_tree.get_object("checkbuttonOcrEnabled")
            },
            "lang": {
                'gui': widget_tree.get_object("comboboxLang"),
                'store': widget_tree.get_object("liststoreOcrLang"),
            },
        }

        actions = {
            "delete-event": (
                [self.window],
                ActionApplySettings(core, self),
            ),
            "toggle_ocr": (
                [self.ocr_settings['enabled']['gui']],
                ActionToggleOCRState(self),
            ),
            "select_scanner": (
                [widget_tree.get_object("comboboxDevices")],
                ActionSelectScanner(self, flatpak)
            ),
            "select_source": (
                [widget_tree.get_object("comboboxScanSources")],
                ActionSelectSource(self)
            ),
            "scan_calibration": (
                [widget_tree.get_object("buttonScanCalibration")],
                ActionScanCalibration(self)
            )
        }

        self.device_settings = {
            "devid": {
                'gui': widget_tree.get_object("comboboxDevices"),
                'stores': {
                    'loaded': widget_tree.get_object("liststoreDevice"),
                },
                'nb_elements': 0,
                'active_idx': -1,
                'active_id': "",
                'children': ['devid', 'source'],
            },
            "has_feeder": False,
            "source": {
                'gui': widget_tree.get_object("comboboxScanSources"),
                'stores': {
                    'loaded': widget_tree.get_object("liststoreScanSources"),
                },
                'nb_elements': 0,
                'active_idx': -1,
                'active_id': "",
                'children': ['resolution'],
            },
            "resolution": {
                'gui': widget_tree.get_object("comboboxResolution"),
                'stores': {
                    'loaded': widget_tree.get_object("liststoreResolution"),
                },
                'nb_elements': 0,
                'active_idx': -1,
                'active_id': "",
                'children': [],
            },
        }

        img_scrollbars = widget_tree.get_object("scrolledwindowCalibration")
        img_canvas = Canvas(img_scrollbars)
        img_canvas.set_visible(True)
        img_scrollbars.add(img_canvas)

        self.calibration = {
            "scan_button": widget_tree.get_object("buttonScanCalibration"),
            "image_gui": img_canvas,
            "image": None,
            "image_eventbox": widget_tree.get_object("eventboxCalibration"),
            "image_scrollbars": img_scrollbars,
            "resolution": DEFAULT_CALIBRATION_RESOLUTION,
            "zoom": widget_tree.get_object("adjustmentZoom"),
        }

        self.grips = None

        self.progressbar = widget_tree.get_object("progressbarScan")
        self.__scan_start = 0.0

        self.job_factories = {
            "device_finder": JobFactoryDeviceFinder(
                self, libinsane,
                core.call_success("paperwork_config_get", 'scanner_devid')
            ),
            "source_finder": JobFactorySourceFinder(
                self, libinsane,
                core.call_success("paperwork_config_get", 'scanner_source')
            ),
            "resolution_finder": JobFactoryResolutionFinder(
                self.core, self, libinsane,
                core.call_success(
                    "paperwork_config_get", 'scanner_resolution'
                ),
            ),
            "scan": JobFactoryCalibrationScan(
                self, libinsane,
                self.device_settings['resolution']['stores']['loaded']
            ),
            "progress_updater": JobFactoryProgressUpdater(self.progressbar),
        }

        try:
            translations = gettext.translation(
                'iso639-3', pycountry.LOCALES_DIR
            )
            logger.info("Language name translations loaded")
        except Exception:
            logger.exception("Unable to load languages translations")
            translations = None

        ocr_tools = pyocr.get_available_tools()

        if len(ocr_tools) == 0:
            short_ocr_langs = []
        else:
            short_ocr_langs = ocr_tools[0].get_available_languages()
        ocr_langs = []
        for short in short_ocr_langs:
            if short in ['equ', 'osd']:
                # ignore some (equ = equation ; osd = orientation detection)
                continue
            llang = self.__get_short_to_long_langs(short)
            if llang:
                if not translations:
                    tlang = llang
                else:
                    tlang = translations.gettext(llang)
                logger.info("Translation: {} | {}".format(llang, tlang))
            if not tlang:
                logger.error("Warning: Long name not found for language "
                             "'%s'." % short)
                logger.warning("  Will use short name as long name.")
                tlang = short
            ocr_langs.append((short, tlang))
        ocr_langs.sort(key=lambda lang: lang[1])

        self.ocr_settings['lang']['store'].clear()
        for (short_lang, long_lang) in ocr_langs:
            self.ocr_settings['lang']['store'].append([long_lang, short_lang])

        for (k, v) in actions.items():
            v[1].connect(v[0])

        self.window.connect("destroy", self.__on_destroy)

        self.display_config()

        self.window.set_visible(True)

        for scheduler in self.local_schedulers:
            scheduler.start()

        job = self.job_factories['device_finder'].make()
        self.schedulers['main'].schedule(job)

    @staticmethod
    def __get_short_to_long_langs(short_lang):
        """
        For each short language name, figures out its long name.

        Arguments:
            short_langs --- Array of strings. Each string is the short name of
            a language. Should be 3 characters long (more should be fine as
            well)

        Returns:
            Tuples: (short name, long name)
        """
        try:
            extra = short_lang[3:]
            short_lang = short_lang[:3]
            long_lang = short_lang
            if extra != "" and (extra[0] == "-" or extra[0] == "_"):
                extra = extra[1:]
            lang = find_language(short_lang, allow_none=True)
            if lang:
                long_lang = lang.name
            if extra != "":
                long_lang += " (%s)" % (extra)
            return long_lang
        except KeyError:
            return None

    def update_active_settings(self):
        for s in self.device_settings.values():
            if not isinstance(s, dict):
                continue
            idx = s['gui'].get_active()
            try:
                s['active_idx'] = idx
                if idx < 0:
                    raise ValueError()
                else:
                    s['active_id'] = s['stores']['loaded'][idx][1]
            except (ValueError, IndexError):
                s['active_idx'] = -1
                s['active_id'] = ""

    def on_finding_start_cb(self, settings):
        settings['gui'].set_sensitive(False)
        ss = (
            [settings] + [
                self.device_settings[x]
                for x in settings['children']
            ]
        )
        for s in ss:
            s['nb_elements'] = 0
            s['active_idx'] = -1
            s['active_id'] = ""
            s['stores']['loaded'].clear()

    def on_device_finding_start_cb(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.on_finding_start_cb(self.device_settings['devid'])
        for element in self.device_settings.values():
            if isinstance(element, dict) and 'gui' in element:
                element['gui'].set_sensitive(False)

    def on_value_found_cb(self, settings,
                          user_name, store_name, active):
        store_line = [user_name, store_name]
        logger.info("Got value [%s]" % store_line)
        settings['stores']['loaded'].append(store_line)
        if active or settings['nb_elements'] == 0:
            settings['active_idx'] = settings['nb_elements']
            settings['active_id'] = store_name
        settings['nb_elements'] += 1

    def on_finding_end_cb(self, settings):
        settings['gui'].set_sensitive(len(settings['stores']['loaded']) > 0)
        settings['gui'].set_model(settings['stores']['loaded'])
        if settings['active_idx'] >= 0:
            settings['gui'].set_active(settings['active_idx'])
        else:
            settings['gui'].set_active(0)

    def on_source_finding_end_cb(self):
        settings = self.device_settings['source']
        sources = [x[1].lower() for x in settings['stores']['loaded']]
        has_feeder = False
        logger.info("Scanner sources: %s" % str(sources))
        for src in sources:
            if "feeder" in src:
                has_feeder = True
            if "adf" in src:
                has_feeder = True
            if has_feeder:
                break
        self.device_settings['has_feeder'] = has_feeder

    def set_mouse_cursor(self, cursor):
        self.window.get_window().set_cursor({
            "Normal": None,
            "Busy": Gdk.Cursor.new(Gdk.CursorType.WATCH),
        }[cursor])

    def on_scan_start(self):
        self.calibration["scan_button"].set_sensitive(False)
        self.set_mouse_cursor("Busy")

        self.calibration['image_gui'].remove_all_drawers()

        self.__scan_start = time.time()

        self.__scan_progress_job = self.job_factories['progress_updater'].make(
            value_min=0.0, value_max=1.0,
            total_time=self.core.call_success(
                "paperwork_config_get", "scan_time"
            )['calibration']
        )
        self.schedulers['progress'].schedule(self.__scan_progress_job)

    def on_scan_info(self, size):
        self.calibration['scan_drawer'] = ScanAnimation(
            (0, 0),
            size, self.calibration['image_gui'].visible_size)
        self.calibration['image_gui'].add_drawer(
            self.calibration['scan_drawer'])

    def on_scan_img(self, previous_line, img):
        self.calibration['scan_drawer'].add_chunk(previous_line, img)

    def _on_scan_end(self):
        self.progressbar.set_fraction(0.0)
        self.schedulers['progress'].cancel(self.__scan_progress_job)
        self.calibration['image_gui'].remove_all_drawers()
        self.set_mouse_cursor("Normal")

    def on_scan_error(self, error):
        self._on_scan_end()
        self.calibration["scan_button"].set_sensitive(False)
        msg = (_("Error while scanning: {}").format(error))
        flags = (Gtk.DialogFlags.MODAL |
                 Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

    def on_scan_done(self, img, scan_resolution):
        scan_stop = time.time()
        t = self.core.call_success("paperwork_config_get", 'scan_time')
        t['calibration'] = (scan_stop - self.__scan_start)
        self.core.call_all("paperwork_config_put", "scan_time", t)

        self._on_scan_end()

        self.calibration['image'] = img
        self.calibration['resolution'] = scan_resolution
        calibration = self.core.call_success(
            "paperwork_config_get", 'scanner_calibration'
        )
        if calibration:
            calibration = calibration[1]
        img_drawer = PillowImageDrawer((0, 0), self.calibration['image'])
        self.calibration['image_gui'].add_drawer(img_drawer)
        self.grips = ImgGripHandler(
            img_drawer, img_drawer.size,
            self.calibration['zoom'],
            default_grips_positions=calibration,
            canvas=self.calibration['image_gui']
        )
        self.calibration['image_gui'].add_drawer(self.grips)
        self.grips.visible = True
        self.calibration["scan_button"].set_sensitive(True)

    def on_scan_canceled(self):
        self.schedulers['progress'].cancel(self.__scan_progress_job)

        self.calibration['image_gui'].unforce_size()
        self.calibration['image_gui'].remove_all_drawers()
        self.calibration['scan_drawer'] = None
        self.set_mouse_cursor("Normal")
        self.calibration["scan_button"].set_sensitive(True)

    def display_config(self):
        self.workdir_chooser.set_current_folder_uri(
            self.core.call_success("paperwork_config_get", 'workdir')
        )

        ocr_enabled = self.core.call_success(
            "paperwork_config_get", 'ocr_enabled'
        )
        ocr_lang = self.core.call_success("paperwork_config_get", "ocr_lang")
        if ocr_lang is None:
            ocr_enabled = False
        self.ocr_settings['enabled']['gui'].set_active(ocr_enabled)

        idx = 0
        for (long_lang, short_lang) in self.ocr_settings['lang']['store']:
            if short_lang == ocr_lang:
                self.ocr_settings['lang']['gui'].set_active(idx)
            idx += 1
        self.set_ocr_opts_state()

        self.network_settings['update'].set_active(
            self.core.call_success("paperwork_config_get", 'check_for_update')
        )
        self.network_settings['statistics'].set_active(
            self.core.call_success("paperwork_config_get", 'send_statistics')
        )

    def set_ocr_opts_state(self):
        ocr_enabled = self.ocr_settings['enabled']['gui'].get_active()
        for (k, v) in self.ocr_settings.items():
            if k == "enabled":
                continue
            v['gui'].set_sensitive(ocr_enabled)

    def __on_destroy(self, window=None):
        logger.info("Settings window destroyed")
        for scheduler in self.local_schedulers:
            scheduler.stop()

    def hide(self):
        """
        Hide and destroy the settings window.
        """
        self.window.destroy()


GObject.type_register(SettingsWindow)
