#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012-2014  Jerome Flesch
#    Copyright (C) 2012  Sebastien Maccagnoni-Munch
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


import gc
import logging
import os
import threading

import gettext

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Notify
import pillowfight

from ... import __version__
from ..aboutdialog import AboutDialog
from ..diag import DiagDialog
from ..import beacon
from ..mainwindow.docs import DocList
from ..mainwindow.docs import DocPropertiesPanel
from ..mainwindow.docs import sort_documents_by_date
from ..mainwindow.pages import JobFactoryImgProcesser
from ..mainwindow.pages import JobFactoryPageBoxesLoader
from ..mainwindow.pages import JobFactoryPageImgLoader
from ..mainwindow.pages import PageDrawer
from ..mainwindow.pages import PageDropHandler
from ..mainwindow.pages import SimplePageDrawer
from ..mainwindow.scan import MultiAnglesScanWorkflowDrawer
from ..mainwindow.scan import ScanWorkflow
from ..mainwindow.scan import SingleAngleScanWorkflowDrawer
from ..multiscan import MultiscanDialog
from ..searchdialog import SearchDialog
from ..settingswindow import SettingsWindow
from ..util import connect_actions
from ..util import get_documentation
from ..util import launch_dbus_filebrowser
from ..util import load_cssfile
from ..util import load_image
from ..util import load_uifile
from ..util import preload_file
from ..util import sizeof_fmt
from ..util.actions import SimpleAction
from ..util.canvas import Canvas
from ..util.canvas.animations import SpinnerAnimation
from ..util.canvas.drawers import Centerer
from ..util.canvas.drawers import PillowImageDrawer
from ..util.canvas.drawers import ProgressBarDrawer
from ..util.canvas.drawers import TextDrawer
from ..util.config import get_scanner
from ..util.dialog import ask_confirmation
from ..util.dialog import popup_no_scanner_found
from ..util.dialog import show_msg
from ..util.jobs import Job
from ..util.jobs import JobFactory
from ..util.jobs import JobScheduler
from paperwork_backend import docexport
from paperwork_backend import docimport
from paperwork_backend import fs
from paperwork_backend.common.page import BasicPage
from paperwork_backend.common.page import DummyPage
from paperwork_backend.docsearch import DocSearch
from paperwork_backend.docsearch import DummyDocSearch
from paperwork_backend.labels import Label
from paperwork_backend.pdf.doc import ExternalPdfDoc


_ = gettext.gettext
logger = logging.getLogger(__name__)


# during tests, we have multiple instatiations of MainWindow(), but we must
# not register the app again
g_must_init_app = True


def check_scanner(main_win, config):
    if config['scanner_devid'].value is not None:
        return True
    main_win.actions['open_settings'][1].do()
    return False


def set_widget_state(widgets, state, cond=lambda widget: True):
    for widget in widgets:
        if cond(widget):
            if isinstance(widget, Gio.Action):
                widget.set_enabled(state)
            else:
                widget.set_sensitive(state)


class JobIndexLoader(Job):
    """
    Reload the doc index
    """

    __gsignals__ = {
        'index-loading-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-loading-progression': (GObject.SignalFlags.RUN_LAST, None,
                                      (GObject.TYPE_FLOAT,
                                       GObject.TYPE_STRING)),
        'index-loading-end': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT, )),
    }

    can_stop = True
    priority = 100

    def __init__(self, factory, job_id, config):
        Job.__init__(self, factory, job_id)
        self.__config = config
        self.started = False
        self.done = False

    def __progress_cb(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        if not self.can_run:
            raise StopIteration()
        if progression % 50 != 0:
            return
        txt = None
        if step == DocSearch.INDEX_STEP_LOADING:
            txt = _('Loading ...')
        else:
            assert()  # unknown progression type
            txt = ""
        if doc is not None:
            txt += (" (%s)" % (doc.name))
        self.emit('index-loading-progression', float(progression) / total, txt)

    def do(self):
        if self.done:
            return
        self.can_run = True
        if not self.started:
            self.emit('index-loading-start')
            self.started = True
        try:
            if (self.__config.CURRENT_INDEX_VERSION !=
                    self.__config['index_version'].value):
                logger.info("Index structure is obsolete."
                            " Must rebuild from scratch")
                docsearch = DocSearch(self.__config['workdir'].value)
                # we destroy the index to force its rebuilding
                docsearch.destroy_index()
                self.__config['index_version'].value = \
                    self.__config.CURRENT_INDEX_VERSION
                self.__config.write()

            if not self.can_run:
                return

            docsearch = DocSearch(
                self.__config['workdir'].value,
                index_in_workdir=self.__config['index_in_workdir'].value
            )
            docsearch.set_language(self.__config['ocr_lang'].value)
            docsearch.reload_index(progress_cb=self.__progress_cb)

            if not self.can_run:
                return

            self.emit('index-loading-end', docsearch)
            self.done = True
        except StopIteration:
            logger.info("Index loading interrupted")

    def stop(self, will_resume=False):
        if not will_resume and not self.done:
            self.emit('index-loading-end', None)
            self.done = True
        self.can_run = False


GObject.type_register(JobIndexLoader)


class JobFactoryIndexLoader(JobFactory):
    def __init__(self, main_window, config):
        JobFactory.__init__(self, "IndexLoader")
        self.__main_window = main_window
        self.__config = config

    def make(self):
        job = JobIndexLoader(self, next(self.id_generator), self.__config)
        job.connect('index-loading-start',
                    lambda job: GLib.idle_add(
                        self.__main_window.on_index_loading_start_cb, job))
        job.connect('index-loading-progression',
                    lambda job, progression, txt:
                    GLib.idle_add(self.__main_window.set_progression,
                                  job, progression, txt))
        job.connect('index-loading-end',
                    lambda loader, docsearch: GLib.idle_add(
                        self.__main_window.on_index_loading_end_cb, loader,
                        docsearch
                    ))
        return job


class JobDocExaminer(Job):
    """
    Look for modified documents
    """

    __gsignals__ = {
        'doc-examination-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'doc-examination-progression': (GObject.SignalFlags.RUN_LAST, None,
                                        (GObject.TYPE_FLOAT,
                                         GObject.TYPE_STRING)),
        'doc-examination-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 50

    def __init__(self, factory, id, main_win, config, docsearch):
        Job.__init__(self, factory, id)
        self.__main_win = main_win
        self.__config = config
        self.docsearch = docsearch
        self.done = False
        self.started = False

        self.labels = set()

    def __progress_cb(self, progression, total, step, doc=None):
        """
        Update the main progress bar
        """
        if not self.can_run:
            raise StopIteration()
        if progression % 10 != 0:
            return
        txt = None
        if step == DocSearch.INDEX_STEP_CHECKING:
            txt = _('Checking ...')
        else:
            assert()  # unknown progression type
            txt = ""
        if doc is not None:
            txt += (" (%s)" % (str(doc)))
        self.emit('doc-examination-progression',
                  float(progression) / total, txt)

    def do(self):
        if self.done:
            return

        self.can_run = True

        if not self.started:
            self.emit('doc-examination-start')
            self.started = True
        self.new_docs = set()  # documents
        self.docs_changed = set()  # documents
        self.docs_missing = set()  # document ids
        try:
            doc_examiner = self.docsearch.get_doc_examiner()
            doc_examiner.examine_rootdir(
                self.__on_new_doc,
                self.__on_doc_changed,
                self.__on_doc_missing,
                self.__on_doc_unchanged,
                self.__progress_cb)
            self.emit('doc-examination-end')
            self.done = True
        except StopIteration:
            logger.info("Document examination interrupted")
            return

    def stop(self, will_resume=False):
        self.can_run = False
        if not will_resume:
            self.emit('doc-examination-end')

    def __on_new_doc(self, doc):
        self.new_docs.add(doc)
        self.labels.update(doc.labels)

    def __on_doc_changed(self, doc):
        self.docs_changed.add(doc)
        self.labels.update(doc.labels)

    def __on_doc_missing(self, docid):
        self.docs_missing.add(docid)

    def __on_doc_unchanged(self, doc):
        self.labels.update(doc.labels)


GObject.type_register(JobDocExaminer)


class JobFactoryDocExaminer(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "DocExaminer")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch):
        job = JobDocExaminer(self, next(self.id_generator),
                             self.__main_win,
                             self.__config, docsearch)
        job.connect(
            'doc-examination-start',
            lambda job: GLib.idle_add(
                self.__main_win.on_doc_examination_start_cb, job))
        job.connect(
            'doc-examination-progression',
            lambda job, progression, txt: GLib.idle_add(
                self.__main_win.set_progression, job, progression, txt))
        job.connect(
            'doc-examination-end',
            lambda job: GLib.idle_add(
                self.__main_win.on_doc_examination_end_cb, job))
        return job


class JobIndexUpdater(Job):
    """
    Update the index
    """

    __gsignals__ = {
        'index-update-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-update-progression': (GObject.SignalFlags.RUN_LAST, None,
                                     (GObject.TYPE_FLOAT,
                                      GObject.TYPE_STRING)),
        'index-update-interrupted': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-update-write': (GObject.SignalFlags.RUN_LAST, None, ()),
        'index-update-end': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = True
    priority = 15

    def __init__(self, factory, id, config, docsearch,
                 new_docs=set(), upd_docs=set(), del_docs=set(),
                 optimize=True):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.__config = config

        self.__condition = threading.Condition()

        self.new_docs = new_docs
        self.upd_docs = upd_docs
        self.del_docs = del_docs

        self.update_only = len(new_docs) == 0 and len(del_docs) == 0

        self.optimize = optimize
        self.index_updater = None
        self.total = (len(self.new_docs) + len(self.upd_docs) +
                      len(self.del_docs))
        self.progression = float(0)

    def __wakeup(self):
        self.__condition.acquire()
        self.__condition.notify_all()
        self.__condition.release()

    def __wait(self):
        # HACK(Jflesch): Make sure the signal is actually taken care
        # of before continuing. Otherwise, on slow computers, the
        # progress bar may not be updated at all until the index
        # update is finished
        self.__condition.acquire()
        GLib.idle_add(self.__wakeup)
        self.__condition.wait(3.0)
        self.__condition.release()

    def do(self):
        # keep in mind that we may have been interrupted and then called back
        # later

        self.can_run = True

        total = len(self.new_docs) + len(self.upd_docs) + len(self.del_docs)
        if total <= 0 and not self.optimize and self.index_updater is None:
            return

        if self.index_updater is None:
            self.emit('index-update-start')
            self.index_updater = self.__docsearch.get_index_updater(
                optimize=self.optimize)

        if not self.can_run:
            logger.warning("Index update interrupted")
            self.emit('index-update-interrupted')
            return

        docs = [
            (_("Indexing new document ..."), self.new_docs,
             self.index_updater.add_doc),
            (_("Reindexing modified document ..."), self.upd_docs,
             self.index_updater.upd_doc),
            (_("Removing deleted document from index ..."), self.del_docs,
             self.index_updater.del_doc),
        ]

        for (op_name, doc_bunch, op) in docs:
            try:
                while True:
                    if not self.can_run:
                        logger.warning("Index update interrupted")
                        self.emit('index-update-interrupted')
                        return
                    doc = doc_bunch.pop()
                    self.emit('index-update-progression',
                              (self.progression * 0.75) / self.total,
                              "%s (%s)" % (op_name, str(doc)))
                    self.__wait()
                    op(doc)
                    self.progression += 1
            except KeyError:
                pass

        if not self.can_run:
            self.emit('index-update-interrupted')
            return

        self.emit('index-update-progression', 0.75,
                  _("Writing index ..."))
        self.emit('index-update-write')
        self.__wait()
        self.index_updater.commit()
        self.index_updater = None
        self.optimize = False
        self.emit('index-update-progression', 1.0, "")
        self.emit('index-update-end')

    def stop(self, will_resume=False):
        self.can_run = False
        if not will_resume:
            self.connect('index-update-interrupted',
                         lambda job:
                         GLib.idle_add(self.index_updater.cancel))


GObject.type_register(JobIndexUpdater)


class JobFactoryIndexUpdater(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "IndexUpdater")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch,
             new_docs=set(), upd_docs=set(), del_docs=set(),
             optimize=True, reload_list=False):
        job = JobIndexUpdater(self, next(self.id_generator), self.__config,
                              docsearch, new_docs, upd_docs, del_docs,
                              optimize)
        job.connect('index-update-start',
                    lambda updater:
                    GLib.idle_add(self.__main_win.on_index_update_start_cb,
                                  updater))
        job.connect('index-update-progression',
                    lambda updater, progression, txt:
                    GLib.idle_add(self.__main_win.set_progression, updater,
                                  progression, txt))
        job.connect('index-update-write',
                    lambda updater:
                    GLib.idle_add(self.__main_win.on_index_update_write_cb,
                                  updater))
        job.connect('index-update-end',
                    lambda updater:
                    GLib.idle_add(self.__main_win.on_index_update_end_cb,
                                  updater))
        if reload_list:
            job.connect('index-update-end',
                        lambda updater:
                        GLib.idle_add(self.__main_win.refresh_doc_list))
        return job


class JobDocSearcher(Job):
    """
    Search the documents
    """
    __gsignals__ = {
        'search-start': (GObject.SignalFlags.RUN_LAST, None,
                         # XXX(Jflesch): TYPE_STRING would turn the Unicode
                         # object into a string object
                         (GObject.TYPE_PYOBJECT, )),
        # user made a typo
        'search-invalid': (GObject.SignalFlags.RUN_LAST, None, ()),
        # array of documents
        'search-results': (GObject.SignalFlags.RUN_LAST, None,
                           # XXX(Jflesch): TYPE_STRING would turn the Unicode
                           # object into a string object
                           (GObject.TYPE_PYOBJECT,
                            GObject.TYPE_PYOBJECT,)),
        # array of suggestions
        'search-suggestions': (GObject.SignalFlags.RUN_LAST, None,
                               (GObject.TYPE_PYOBJECT,)),
    }

    can_stop = True
    priority = 500

    def __init__(self, factory, id, config, docsearch, sort_func,
                 search_type, search):
        Job.__init__(self, factory, id)
        self.search = search
        self.__search_type = search_type
        self.__docsearch = docsearch
        self.__sort_func = sort_func
        self.__config = config

    def do(self):
        self.can_run = True

        self._wait(0.5)
        if not self.can_run:
            return

        self.emit('search-start', self.search)

        try:
            logger.info("Searching: [%s]" % self.search)
            documents = self.__docsearch.find_documents(
                self.search,
                search_type=self.__search_type)
        except Exception as exc:
            logger.error("Invalid search: [%s]" % self.search)
            logger.error("Exception was: %s: %s" % (type(exc), str(exc)))
            logger.exception(exc)
            self.emit('search-invalid')
            return
        if not self.can_run:
            return

        if self.search == u"":
            # when no specific search has been done, the sorting is always
            # the same
            sort_documents_by_date(documents)
        else:
            self.__sort_func(documents)
        self.emit('search-results', self.search, documents)

        if not self.can_run:
            logger.info("Search cancelled. Won't look for suggestions")
            return
        suggestions = self.__docsearch.find_suggestions(self.search)
        self.emit('search-suggestions', suggestions)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobDocSearcher)


class JobFactoryDocSearcher(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "Search")
        self.__main_win = main_win
        self.__config = config

    def make(self, docsearch, sort_func, search_type, search):
        job = JobDocSearcher(self, next(self.id_generator), self.__config,
                             docsearch, sort_func, search_type, search)
        job.connect('search-start', lambda searcher, search:
                    GLib.idle_add(self.__main_win.on_search_start_cb, search))
        job.connect('search-results',
                    lambda searcher, search, documents:
                    GLib.idle_add(self.__main_win.on_search_results_cb,
                                  search, documents))
        job.connect('search-invalid',
                    lambda searcher: GLib.idle_add(
                        self.__main_win.on_search_invalid_cb))
        job.connect('search-suggestions',
                    lambda searcher, suggestions:
                    GLib.idle_add(self.__main_win.on_search_suggestions_cb,
                                  suggestions))
        return job


class JobLabelPredictor(Job):
    """
    Predicts what labels should be on a document
    """

    __gsignals__ = {
        # array of labels (strings)
        'predicted-labels': (GObject.SignalFlags.RUN_LAST, None,
                             (
                                 GObject.TYPE_PYOBJECT,  # doc
                                 GObject.TYPE_PYOBJECT,  # array of labels
                             )),
    }

    can_stop = True
    priority = 10

    def __init__(self, factory, id, docsearch, doc):
        Job.__init__(self, factory, id)
        self.__docsearch = docsearch
        self.doc = doc

    def _progress_cb(self, current, total):
        if not self.can_run:
            raise StopIteration()

    def do(self):
        self.can_run = True
        try:
            guessed_labels = self.__docsearch.guess_labels(self.doc)
            guessed_labels = [label for (label, scores) in guessed_labels]
            logger.info("Predicted labels on document [%s]: [%s]"
                        % (self.doc.docid, guessed_labels))
            self.emit('predicted-labels', self.doc, guessed_labels)
        except StopIteration:
            return

    def stop(self, will_resume=False):
        self.can_run = False


GObject.type_register(JobLabelPredictor)


class JobFactoryLabelPredictorOnNewDoc(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "Label predictor (on new doc)")
        self.__main_win = main_win

    def make(self, doc):
        job = JobLabelPredictor(self, next(self.id_generator),
                                self.__main_win.docsearch, doc)
        return job


class JobExportPreviewer(Job):
    __gsignals__ = {
        'export-preview-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'export-preview-done': (GObject.SignalFlags.RUN_LAST, None,
                                (GObject.TYPE_INT, GObject.TYPE_PYOBJECT,)),
    }

    can_stop = True
    priority = 500

    def __init__(self, factory, id, exporter):
        Job.__init__(self, factory, id)
        self.__exporter = exporter

    def do(self):
        self.can_run = True
        self._wait(0.7)
        if not self.can_run:
            return

        self.emit('export-preview-start')

        size = self.__exporter.estimate_size()
        if not self.can_run:
            return

        img = self.__exporter.get_img()
        if not self.can_run:
            return

        drawer = PillowImageDrawer((0, 0), img)
        if not self.can_run:
            return

        self.emit('export-preview-done', size, drawer)

    def stop(self, will_resume=False):
        self.can_run = False
        self._stop_wait()


GObject.type_register(JobExportPreviewer)


class JobFactoryExportPreviewer(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "ExportPreviewer")
        self.__main_win = main_win

    def make(self, exporter):
        job = JobExportPreviewer(self, next(self.id_generator), exporter)
        job.connect('export-preview-start',
                    lambda job:
                    GLib.idle_add(self.__main_win.on_export_preview_start))
        job.connect('export-preview-done',
                    lambda job, size, pixbuf:
                    GLib.idle_add(self.__main_win.on_export_preview_done,
                                  size, pixbuf))
        return job


class JobExport(Job):
    __gsignals__ = {
        'export-start': (GObject.SignalFlags.RUN_LAST, None, ()),
        'export-progress': (GObject.SignalFlags.RUN_LAST, None,
                            (GObject.TYPE_INT, GObject.TYPE_INT)),
        'export-done': (GObject.SignalFlags.RUN_LAST, None,
                        (GObject.TYPE_PYOBJECT, )),  # exporter
        'export-error': (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_PYOBJECT,  # exporter
                          GObject.TYPE_PYOBJECT)),  # exception
    }

    can_stop = False
    priority = 500

    def __init__(self, factory, id, exporter, target_path):
        Job.__init__(self, factory, id)
        self._exporter = exporter
        self._target_path = target_path

    def _on_progress_cb(self, current, total):
        self.emit('export-progress', current, total)

    def do(self):
        self.emit('export-start')

        try:
            self._exporter.save(self._target_path, self._on_progress_cb)
        except Exception as exc:
            logger.exception("Export failed")
            self.emit('export-error', self._exporter, exc)
            raise

        self.emit('export-done', self._exporter)


GObject.type_register(JobExport)


class JobFactoryExport(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "Export")
        self.__main_win = main_win

    def make(self, exporter, target_path):
        job = JobExport(self, next(self.id_generator), exporter, target_path)
        job.connect('export-start',
                    lambda job:
                    GLib.idle_add(self.__main_win.on_export_start))
        job.connect('export-progress',
                    lambda job, current, total:
                    GLib.idle_add(self.__main_win.on_export_progress,
                                  current, total))
        job.connect('export-error',
                    lambda job, exporter, error:
                    GLib.idle_add(self.__main_win.on_export_error,
                                  exporter, error))
        job.connect('export-done',
                    lambda job, exporter:
                    GLib.idle_add(self.__main_win.on_export_done, exporter))
        return job


class JobPageEditor(Job):
    __gsignals__ = {
        'page-editing-img-edit': (GObject.SignalFlags.RUN_LAST, None,
                                  (GObject.TYPE_PYOBJECT, )),
        'page-editing-done': (GObject.SignalFlags.RUN_LAST, None,
                              (GObject.TYPE_PYOBJECT, )),
    }

    can_stop = False
    priority = 10

    def __init__(self, factory, id, page, changes=[]):
        Job.__init__(self, factory, id)
        self.__page = page
        self.__changes = changes[:]

    def do(self):
        self.emit('page-editing-img-edit', self.__page)
        try:
            img = self.__page.img
            for change in self.__changes:
                img = change.do(img, 1.0)
            self.__page.img = img
        finally:
            self.emit('page-editing-done', self.__page)


GObject.type_register(JobPageEditor)


class JobPageImgRenderer(Job):
    __gsignals__ = {
        'rendered': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_INT, GObject.TYPE_INT,
                         GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)),
        'rendering-error': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    can_stop = False
    priority = 100

    def __init__(self, factory, id, page):
        Job.__init__(self, factory, id)
        self.page = page

    def do(self):
        try:
            self.emit("rendered",
                      self.page.page_nb, self.page.doc.nb_pages,
                      self.page.img, self.page.boxes)
        except:  # noqa: E722
            # TODO(Jflesch)
            # We get "MemoryError" sometimes ? oO
            self.emit("rendering-error")
            raise


class JobFactoryPageImgRenderer(JobFactory):
    def __init__(self, main_win):
        JobFactory.__init__(self, "PageImgRenderer")
        self.__main_win = main_win

    def make(self, page):
        job = JobPageImgRenderer(self, next(self.id_generator), page)
        job.connect("rendered",
                    lambda renderer, page_nb, total_pages, img, boxes:
                    GLib.idle_add(self.__main_win.on_page_img_rendered,
                                  renderer, page_nb, total_pages))
        job.connect("rendering-error",
                    lambda renderer: GLib.idle_add(
                        self.__main_win.on_page_img_rendering_error, renderer))
        return job


class JobImporter(Job):
    __gsignals__ = {
        'import-error': (GObject.SignalFlags.RUN_LAST, None,
                         (GObject.TYPE_PYOBJECT, )),
        'no-doc-imported': (GObject.SignalFlags.RUN_LAST, None, ()),
        'import-ok': (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_PYOBJECT,
                       GObject.TYPE_PYOBJECT,
                       GObject.TYPE_PYOBJECT,
                       )),
    }

    can_stop = False
    priority = 150

    def __init__(self, factory, id, main_win, config, importer, file_uris):
        Job.__init__(self, factory, id)
        self.__main_win = main_win
        self.__config = config
        self.importer = importer
        self.file_uris = file_uris

    class IndexAdder(object):
        def __init__(self, main_win, page_iterator, must_add_labels=False):
            self._main_win = main_win
            self._page_iterator = page_iterator
            self.must_add_labels = must_add_labels

            self._docs_to_label_predict = set()
            self._docs_to_upd = set()

        def start(self):
            self._ocr_next_page()

        def _ocr_next_page(self):
            try:
                while True:
                    page = next(self._page_iterator)
                    logger.info("Examining page %s" % str(page))
                    if len(page.boxes) <= 0:
                        break
                    self._add_doc_to_checklists(page.doc)
                    self._main_win.on_page_img_rendered(
                        None, page.page_nb, page.doc.nb_pages
                    )
            except StopIteration:
                logger.info("All the target pages have been examined")
                if len(self._docs_to_label_predict) > 0:
                    self._predict_labels()
                else:
                    self._update_index()
                return

            # found a page where we need to run the OCR
            renderer = self._main_win.job_factories['page_img_renderer']
            renderer = renderer.make(page)
            renderer.connect("rendered",
                             lambda _, page_nb, nb_pages, img, boxes:
                             GLib.idle_add(self._ocr,
                                           page, img, boxes))
            self._main_win.schedulers['main'].schedule(renderer)

        def _ocr(self, page, page_img, boxes):
            if len(boxes) <= 0:
                logger.info("Doing OCR on %s" % str(page))
                self._main_win.show_doc(page.doc)
                scan_workflow = self._main_win.make_scan_workflow()
                drawer = self._main_win.make_scan_workflow_drawer(
                    scan_workflow, single_angle=True, page=page)
                self._main_win.add_scan_workflow(page.doc, drawer,
                                                 page_nb=page.page_nb)
                scan_workflow.connect('process-done',
                                      lambda scan_workflow, img, boxes:
                                      GLib.idle_add(self._on_page_ocr_done,
                                                    scan_workflow, img,
                                                    boxes, page))
                scan_workflow.ocr(page_img, angles=1)
            else:
                logger.info("Imported page %s already has text" % page)
                self._add_doc_to_checklists(page.doc)
                GLib.idle_add(self._ocr_next_page)

        def _on_page_ocr_done(self, scan_workflow, img, boxes, page):
            if page.can_edit:
                page.img = img
            if boxes is None:
                logger.warning("No word found ?")
                boxes = []
            page.boxes = boxes

            logger.info("OCR done on %s" % str(page))
            self._main_win.remove_scan_workflow(scan_workflow)
            self._main_win.show_page(page, force_refresh=True)
            self._add_doc_to_checklists(page.doc)
            self._ocr_next_page()

        def _add_doc_to_checklists(self, doc):
            self._docs_to_upd.add(doc)
            if self.must_add_labels:
                self._docs_to_label_predict.add(doc)

        def _predict_labels(self):
            for doc in self._docs_to_label_predict:
                logger.info("Predicting labels on doc %s"
                            % str(doc))
                factory = self._main_win.job_factories[
                    'label_predictor_on_new_doc'
                ]
                job = factory.make(doc)
                job.connect("predicted-labels",
                            self._on_predicted_labels)
                self._main_win.schedulers['main'].schedule(job)

        def _on_predicted_labels(self, predictor, doc, predicted_labels):
            GLib.idle_add(self._on_predicted_labels2, doc, predicted_labels)

        def _on_predicted_labels2(self, doc, predicted_labels):
            logger.info("Label predicted on doc %s" % str(doc))
            for label in self._main_win.docsearch.label_list:
                if label in predicted_labels:
                    self._main_win.docsearch.add_label(doc, label,
                                                       update_index=False)
            self._docs_to_label_predict.remove(doc)
            if len(self._docs_to_label_predict) <= 0:
                self._update_index()
            self._main_win.refresh_label_list()

        def _update_index(self):
            logger.info("Updating index for %d docs"
                        % len(self._docs_to_upd))
            job = self._main_win.job_factories['index_updater'].make(
                self._main_win.docsearch, new_docs=self._docs_to_upd,
                optimize=False, reload_list=True)
            self._main_win.schedulers['index'].schedule(job)
            self._docs_to_upd = set()

    def do(self):
        self.__main_win.set_mouse_cursor("Busy")
        try:
            try:
                import_result = self.importer.import_doc(
                    self.file_uris, self.__main_win.docsearch,
                    self.__main_win.doc
                )
            finally:
                self.__main_win.set_mouse_cursor("Normal")
        except Exception as exc:
            self.emit('import-error', str(exc))
            raise

        if not import_result.has_import:
            self.emit('no-doc-imported')
            return

        nb_docs = len(import_result.new_docs) + len(import_result.upd_docs)
        nb_pages = (
            len(import_result.new_docs_pages) +
            len(import_result.upd_docs_pages)
        )
        logger.info("Imported %d docs and %d pages" % (nb_docs, nb_pages))
        logger.info("- New docs: {}".format(import_result.new_docs))
        logger.info("- Upd docs: {}".format(import_result.upd_docs))
        logger.info("- New pages: {}".format(import_result.new_docs_pages))
        logger.info("- Upd pages: {}".format(import_result.upd_docs_pages))

        if import_result.select_doc:
            self.__main_win.show_doc(
                import_result.select_doc,
                force_refresh=True
            )

        if import_result.select_page:
            self.__main_win.show_page(
                import_result.select_page,
                force_refresh=True
            )

        set_widget_state(self.__main_win.need_doc_widgets, True)

        new_doc_pages = import_result.new_docs_pages
        upd_doc_pages = import_result.upd_docs_pages

        if upd_doc_pages != []:
            logger.info("Adding %d pages to index (auto labels=False)",
                        len(upd_doc_pages))
            self.IndexAdder(
                self.__main_win, iter(upd_doc_pages), must_add_labels=False
            ).start()
        if new_doc_pages != []:
            logger.info("Adding %d pages to index (auto labels=True)",
                        len(new_doc_pages))
            self.IndexAdder(
                self.__main_win, iter(new_doc_pages), must_add_labels=True
            ).start()

        self.emit(
            'import-ok',
            import_result.stats, import_result.select_doc,
            import_result.imported_file_uris
        )


GObject.type_register(JobImporter)


class JobFactoryImporter(JobFactory):
    def __init__(self, main_win, config):
        JobFactory.__init__(self, "Importer")
        self._main_win = main_win
        self._config = config

    def make(self, importer, file_uris):
        return JobImporter(self, next(self.id_generator),
                           self._main_win, self._config,
                           importer, file_uris)


class ActionNewDocument(SimpleAction):
    """
    Starts a new docume.
    """
    def __init__(self, doclist, main_win):
        SimpleAction.__init__(self, "New document")
        self.__doclist = doclist
        self.__main_win = main_win

    def do(self):
        SimpleAction.do(self)

        self.__main_win.allow_multiselect = False
        self.__doclist.open_new_doc()
        self.__doclist.gui['scrollbars'].get_vadjustment().set_value(0)


class ActionUpdateSearchResults(SimpleAction):
    """
    Update search results
    """
    def __init__(self, main_window, refresh_pages=True):
        SimpleAction.__init__(self, "Update search results")
        self.__main_win = main_window
        self.__refresh_pages = refresh_pages

    def do(self):
        SimpleAction.do(self)
        self.__main_win.searchbar.reset()
        self.__main_win.refresh_doc_list()

        if self.__refresh_pages:
            self.__main_win.refresh_boxes()


class ActionOpenSearchDialog(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open search dialog")
        self.__main_win = main_window
        self.dialog = None  # for tests

    def do(self):
        logger.info("Opening search dialog")
        self.dialog = SearchDialog(self.__main_win)
        response = self.dialog.run()
        if response == 1:
            logger.info("Search dialog: apply")
            search = self.dialog.get_search_string()
            self.__main_win.search_field.set_text(search)
        else:
            logger.info("Search dialog: cancelled")
        self.dialog = None


class ActionOpenViewSettings(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open view settings")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.popovers['view_settings'].set_relative_to(
            self.__main_win.actions['open_view_settings'][0][0]
        )
        self.__main_win.popovers['view_settings'].set_visible(True)


class ActionShowDocumentAsPaged(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show document page per page")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.set_layout('paged')


class ActionShowDocumentAsGrid(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show document as a grid")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.set_layout('grid')


class ActionSwitchSorting(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Switch sorting")
        self.__main_win = main_window
        self.__config = config
        self.__upd_search_results_action = \
            ActionUpdateSearchResults(main_window, refresh_pages=False)

    def do(self):
        SimpleAction.do(self)
        (sorting_name, unused) = self.__main_win.get_doc_sorting()
        logger.info("Document sorting: %s" % sorting_name)
        self.__config['result_sorting'].value = sorting_name
        self.__config.write()
        self.__upd_search_results_action.do()


class ActionMovePageIndex(SimpleAction):
    def __init__(self, main_window, relative=True, value=0):
        if relative:
            txt = "previous"
            if value > 0:
                txt = "next"
        else:
            if value < 0:
                txt = "last"
            else:
                txt = "page %d" % (value)
        SimpleAction.__init__(self, ("Show the %s page" % (txt)))
        self.relative = relative
        self.value = value
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        page_idx = self.__main_win.page.page_nb
        if self.relative:
            page_idx += self.value
        elif self.value < 0:
            page_idx = self.__main_win.doc.nb_pages - 1
        else:
            page_idx = self.value
        if page_idx < 0 or page_idx >= self.__main_win.doc.nb_pages:
            return
        page = self.__main_win.doc.pages[page_idx]
        self.__main_win.show_page(page, force_refresh=True)


class ActionOpenPageNb(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Show a page (selected on its number)")
        self.__main_win = main_window

    def entry_changed(self, entry):
        pass

    def do(self):
        SimpleAction.do(self)
        page_nb = self.__main_win.page_nb['current'].get_text()
        try:
            page_nb = int(page_nb) - 1
        except ValueError:
            return
        if page_nb > self.__main_win.doc.nb_pages:
            page_nb = self.__main_win.doc.nb_pages - 1
        if page_nb < 0:
            return
        page = self.__main_win.doc.pages[page_nb]
        self.__main_win.show_page(page)


class ActionUpdPageSizes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Reload current page")
        self.__main_win = main_window
        self.enabled = True

    def do(self):
        if not self.enabled:
            return
        SimpleAction.do(self)
        mw = self.__main_win
        mw.zoom_level['auto'] = False
        mw.update_page_sizes()
        mw.img['canvas'].recompute_size(upd_scrollbar_values=True)
        mw.img['canvas'].redraw(checked=True)


class ActionRefreshBoxes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Refresh current page boxes")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_boxes()


class ActionToggleAllBoxes(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Toggle all boxes visibility")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        self.__main_win.refresh_boxes()


class ActionToggleLabel(object):
    def __init__(self, main_window):
        self.__main_win = main_window

    def toggle_cb(self, renderer, objpath):
        label = self.__main_win.lists['labels']['model'][objpath][2]
        if label not in self.__main_win.doc.labels:
            logger.info("Action: Adding label '%s' on document '%s'"
                        % (label.name, str(self.__main_win.doc)))
            self.__main_win.docsearch.add_label(self.__main_win.doc, label,
                                                update_index=False)
        else:
            logger.info("Action: Removing label '%s' on document '%s'"
                        % (label.name, self.__main_win.doc))
            self.__main_win.docsearch.remove_label(self.__main_win.doc, label,
                                                   update_index=False)
        self.__main_win.refresh_label_list()
        self.__main_win.refresh_docs({self.__main_win.doc},
                                     redo_thumbnails=False)
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch, upd_docs={self.__main_win.doc},
            optimize=False)
        self.__main_win.schedulers['index'].schedule(job)

    def connect(self, cellrenderers):
        for cellrenderer in cellrenderers:
            cellrenderer.connect('toggled', self.toggle_cb)


class ActionOpenDocDir(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open doc dir")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        if os.name == 'nt':
            os.startfile(self.__main_win.docsearch.fs.unsafe(
                self.__main_win.doc.path))
            return
        if self.__main_win.flatpak:
            launch_dbus_filebrowser(self.__main_win.doc.path)
            return
        if hasattr(Gtk, 'show_uri_on_window'):
            Gtk.show_uri_on_window(
                self.__main_win.window,
                self.__main_win.doc.path,
                Gdk.CURRENT_TIME
            )
            return
        Gtk.show_uri(
            self.__main_win.window.get_window().get_screen(),
            self.__main_win.doc.path,
            Gdk.CURRENT_TIME
        )


class ActionPrintDoc(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Open print dialog")
        self.__main_win = main_window

    class PrintPageCb(object):
        def __init__(self, doc, keep_refs):
            self.doc = doc
            self.keep_refs = keep_refs

        def print_page_cb(self, print_op, print_context, page_nb):
            self.doc.print_page_cb(print_op, print_context, page_nb,
                                   self.keep_refs)

    def do(self):
        SimpleAction.do(self)

        keep_refs = {}
        cb = self.PrintPageCb(self.__main_win.doc, keep_refs)

        print_settings = Gtk.PrintSettings()
        print_op = Gtk.PrintOperation()
        print_op.set_print_settings(print_settings)
        print_op.set_n_pages(self.__main_win.doc.nb_pages)
        print_op.set_current_page(self.__main_win.page.page_nb)
        print_op.set_use_full_page(False)
        print_op.set_job_name(str(self.__main_win.doc))
        print_op.set_export_filename(str(self.__main_win.doc) + ".pdf")
        print_op.set_allow_async(False)
        print_op.connect("draw-page", cb.print_page_cb)
        print_op.set_embed_page_setup(True)
        print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG,
                     self.__main_win.window)
        del keep_refs


class ActionOpenSettings(SimpleAction):
    def __init__(self, main_window, config, libinsane):
        SimpleAction.__init__(self, "Open settings dialog")
        self.__main_win = main_window
        self.__config = config
        self.__libinsane = libinsane
        # for tests only / prevent also the dialog from being GC
        self.dialog = None

    def do(self):
        SimpleAction.do(self)
        self.dialog = SettingsWindow(
            self.__main_win.schedulers['main'],
            self.__main_win.window, self.__config,
            self.__libinsane,
            self.__main_win.flatpak
        )
        self.dialog.connect("need-reindex", self.__reindex_cb)
        self.dialog.connect("config-changed", self.__on_config_changed_cb)

    def __reindex_cb(self, settings_window):
        self.__main_win.actions['reindex'][1].do()

    def __on_config_changed_cb(self, setttings_window):
        self.__main_win.docsearch.set_language(self.__config['ocr_lang'].value)
        set_widget_state(
            self.__main_win.actions['multi_scan'][0],
            self.__config['scanner_has_feeder'].value
        )


class ActionSingleScan(SimpleAction):
    def __init__(self, main_window, config, libinsane):
        SimpleAction.__init__(self, "Scan a single page")
        self.__main_win = main_window
        self.__config = config
        self.__libinsane = libinsane

    def __on_scan_ocr_canceled(self, scan_workflow):
        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        if self.__main_win.doc.docid == docid:
            self.__main_win.show_page(self.__main_win.doc.pages[-1],
                                      force_refresh=True)

    def __on_scan_error(self, scan_workflow, exc):
        if isinstance(exc, StopIteration):
            msg = _("Scan failed: No paper found")
        else:
            msg = _("Scan failed: {}").format(str(exc))
        flags = (Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

        if not scan_workflow:
            return
        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        if self.__main_win.doc.docid == docid:
            self.__main_win.show_page(self.__main_win.doc.pages[-1],
                                      force_refresh=True)

    def __on_ocr_done(self, scan_workflow, img, line_boxes):
        docid = self.__main_win.remove_scan_workflow(scan_workflow)
        self.__main_win.add_page(docid, img, line_boxes)

    def do(self, call_at_end=None):
        SimpleAction.do(self)
        self.__main_win.set_mouse_cursor("Busy")

        try:
            if not check_scanner(self.__main_win, self.__config):
                return

            try:
                (dev, resolution) = get_scanner(
                    self.__config, self.__libinsane
                )
            except Exception as exc:
                logger.warning("Exception while configuring scanner: %s: %s."
                               " Assuming scanner is not connected",
                               type(exc), exc)
                logger.exception(exc)
                popup_no_scanner_found(self.__main_win.window, str(exc))
                return
            try:
                scan_session = dev.scan_start()
            except Exception as exc:
                logger.warning("Error while scanning: {}".format(str(exc)))
                self.__on_scan_error(None, exc)
                raise
        finally:
            self.__main_win.set_mouse_cursor("Normal")

        scan_workflow = self.__main_win.make_scan_workflow()
        scan_workflow.connect('scan-canceled', lambda scan_workflow:
                              GLib.idle_add(self.__on_scan_ocr_canceled,
                                            scan_workflow))
        scan_workflow.connect('scan-error', lambda scan_scan, exc:
                              GLib.idle_add(self.__on_scan_error,
                                            scan_workflow,
                                            exc))
        scan_workflow.connect('ocr-canceled', lambda scan_workflow:
                              GLib.idle_add(self.__on_scan_ocr_canceled,
                                            scan_workflow))
        scan_workflow.connect('process-done', lambda scan_workflow, img, boxes:
                              GLib.idle_add(self.__on_ocr_done, scan_workflow,
                                            img, boxes))
        if call_at_end:
            scan_workflow.connect(
                'process-done',
                lambda scan_workflow, img, boxes:
                GLib.idle_add(call_at_end)
            )

        drawer = self.__main_win.make_scan_workflow_drawer(
            scan_workflow, single_angle=False)
        self.__main_win.add_scan_workflow(self.__main_win.doc, drawer)
        scan_workflow.scan_and_ocr(resolution, scan_session)
        return scan_workflow


class ActionMultiScan(SimpleAction):
    def __init__(self, main_window, config, libinsane):
        SimpleAction.__init__(self, "Scan multiples pages")
        self.__main_win = main_window
        self.__config = config
        self.__libinsane = libinsane
        # for tests/screenshots only
        self.dialog = None

    def do(self):
        SimpleAction.do(self)
        if not check_scanner(self.__main_win, self.__config):
            return
        self.dialog = MultiscanDialog(
            self.__main_win, self.__config, self.__libinsane
        )
        self.dialog.connect("need-show-page",
                            lambda ms_dialog, page:
                            GLib.idle_add(self.__show_page, page))

    def __show_page(self, page):
        self.__main_win.refresh_doc_list()
        self.__main_win.show_page(page)


class ActionImport(SimpleAction):
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Import file(s)")
        self.__main_win = main_window
        self.__config = config
        self._select_file_dialog = None
        self.notification = None

    def __select_file_cb(self, dialog, response):
        if response != 0:
            logger.info("Import: Canceled by user")
            dialog.destroy()
            return None
        file_uris = dialog.get_uris()
        dialog.destroy()
        logger.info("Import: %s", file_uris)
        GLib.idle_add(self._do_import, file_uris)

    def __add_filters(self, dialog):
        all_mimes = []

        filters = []
        for importer in docimport.IMPORTERS:
            mimes = importer.get_select_mime_types()
            for (name, mime) in mimes:
                all_mimes.append(mime)
                ffilter = Gtk.FileFilter()
                ffilter.add_mime_type(mime)
                ffilter.set_name(name)
                filters.append(ffilter)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("All supported file formats"))
        for mime in all_mimes:
            filter_all.add_mime_type(mime)
        filter_any = Gtk.FileFilter()
        filter_any.set_name(_("Any file"))
        filter_any.add_pattern("*.*")

        dialog.add_filter(filter_any)
        dialog.add_filter(filter_all)
        for ffilter in filters:
            dialog.add_filter(ffilter)
        dialog.set_filter(filter_all)

    def __select_file(self):
        widget_tree = load_uifile(
            os.path.join("import", "importfileselector.glade"))
        dialog = widget_tree.get_object("filechooserdialog")
        dialog.set_transient_for(self.__main_win.window)
        dialog.set_local_only(False)
        dialog.set_select_multiple(True)
        self.__add_filters(dialog)

        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(self.__select_file_cb, dialog, response))

        self._select_file_dialog = dialog
        dialog.show_all()

    def __select_importer(self, importers):
        widget_tree = load_uifile(
            os.path.join("import", "importaction.glade"))
        combobox = widget_tree.get_object("comboboxImportAction")
        importer_list = widget_tree.get_object("liststoreImportAction")
        dialog = widget_tree.get_object("dialogImportSelect")

        importer_list.clear()
        for importer in importers:
            importer_list.append([str(importer), importer])

        response = dialog.run()
        active_idx = combobox.get_active()

        dialog.destroy()
        if response <= 0:
            raise Exception("Import cancelled by user")

        return importer_list[active_idx][1]

    def __no_importer(self, file_uris):
        msg = (_("Don't know how to import '%s'. Sorry.") %
               (file_uris))
        flags = (Gtk.DialogFlags.MODAL |
                 Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

    def __no_doc_imported(self):
        msg = _("No new document to import found")
        flags = (Gtk.DialogFlags.MODAL |
                 Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

    def __import_error(self, msg):
        msg = _("Import failed: {}").format(msg)
        flags = (Gtk.DialogFlags.MODAL |
                 Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.__main_win.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()

    def __import_ok(self, stats, file_uris):
        msg = _("Imported:\n")
        for (k, v) in stats.items():
            msg += ("- {}: {}\n".format(k, v))
        msg = msg.strip()

        if "actions" in Notify.get_server_caps():
            notification = Notify.Notification.new(
                _("Import successful"),
                msg,
                "document-new"
            )
            notification.add_action(
                "delete",
                _("Delete imported files"),
                self._delete_files, file_uris
            )
            notification.show()
            self.notification = notification  # keep a ref on the notif
        else:
            # fall back on classical ugly popup
            msg += "\n"
            msg += _("Would you like to move the original file(s) to trash?\n")
            ask_confirmation(self.__main_win.window, self.__delete_files,
                             msg=msg, file_uris=file_uris)

    def _delete_files(self, notification, action, file_uris=[],
                      *args, **kwargs):
        self.notification = None
        logger.info("Moving imported file(s) to trash ...")
        GLib.idle_add(self.__delete_files, file_uris)

    def __delete_files(self, file_uris=[]):
        for file_uri in file_uris:
            logger.info("Moving {} to trash ...".format(file_uri))
            gfile = Gio.File.new_for_uri(file_uri)
            trashed = False
            try:
                trashed = gfile.trash()
            except Exception as exc:
                logger.warning(
                    "Failed to move file %s to trash. Will delete it",
                    file_uri, exc_info=exc
                )
            if not trashed:
                gfile.delete()
        notification = Notify.Notification.new(
            _("Imported file(s) deleted"),
            None,
            "edit-delete"
        )
        notification.show()

    def do(self):
        SimpleAction.do(self)
        GLib.idle_add(self._do)

    def _do(self):
        self.__select_file()

    def _do_import(self, file_uris):
        for file_uri in file_uris:
            gfile = Gio.File.new_for_uri(file_uri)
            file_type = gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            if file_type == Gio.FileType.DIRECTORY or not gfile.has_parent():
                # If the user imported a directory, assume they will again
                # import the same directory later (useful for people just
                # keeping adding PDF files in the same directory)
                logger.info("Adding %s to recently used files", file_uri)
                Gtk.RecentManager().add_item(file_uri)
            else:
                # If the user imported a file, assume they won't import it
                # twice but they may import again other files from the same
                # directory
                parent = gfile.get_parent()
                logger.info("Adding %s to recently used files",
                            parent.get_uri())
                Gtk.RecentManager().add_item(parent.get_uri())

        importers = docimport.get_possible_importers(
            file_uris, self.__main_win.doc)
        if len(importers) <= 0:
            self.__no_importer(file_uris)
            return
        elif len(importers) > 1:
            importer = self.__select_importer(importers)
        else:
            importer = importers[0]

        job_importer = self.__main_win.job_factories['importer']
        job_importer = job_importer.make(importer, file_uris)
        job_importer.connect('no-doc-imported',
                             lambda _: GLib.idle_add(self.__no_doc_imported))
        job_importer.connect(
            'import-error',
            lambda _, msg: GLib.idle_add(self.__import_error, msg)
        )
        job_importer.connect(
            'import-ok',
            lambda _, stats, doc, uris: GLib.idle_add(self.__import_ok, stats,
                                                      uris)
        )
        self.__main_win.schedulers['main'].schedule(job_importer)


class ActionDeletePage(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Delete page")
        self.__main_win = main_window
        self.page = None

    def do(self, page=None):
        """
        Ask for confirmation and then delete the page being viewed.
        """
        self.page = page
        ask_confirmation(self.__main_win.window, self._do)

    def _do(self):
        page = self.page

        if page is None:
            page = self.__main_win.page
        doc = page.doc

        SimpleAction.do(self)
        logger.info("Deleting ...")
        page.destroy()
        logger.info("Deleted")
        self.__main_win.page = None
        set_widget_state(self.__main_win.need_page_widgets, False)
        if len(doc.pages) > 0:
            self.__main_win.refresh_docs({doc})
        else:
            self.__main_win.refresh_doc_list()
        self.__main_win.show_doc(self.__main_win.doc, force_refresh=True)

        if doc.nb_pages <= 0:
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch, del_docs={doc},
                optimize=False)
        else:
            job = self.__main_win.job_factories['index_updater'].make(
                self.__main_win.docsearch, upd_docs={doc}, optimize=False)
        self.__main_win.schedulers['index'].schedule(job)


class ActionRedoOCR(SimpleAction):
    def __init__(self, name, main_window, ask_confirmation=True):
        SimpleAction.__init__(self, name)
        self._main_win = main_window
        self.ask_confirmation = ask_confirmation
        self._iterator = None

    def _do_next_page(self, page_iterator, docs_done=None):
        try:
            page = next(page_iterator)
        except StopIteration:
            logger.info("OCR has been redone on all the target pages")
            raise

        if page.doc != self._main_win.doc:
            self._main_win.show_doc(page.doc)

        logger.info("Redoing OCR on %s" % str(page))
        scan_workflow = self._main_win.make_scan_workflow()
        drawer = self._main_win.make_scan_workflow_drawer(
            scan_workflow, single_angle=True, page=page)
        self._main_win.add_scan_workflow(page.doc, drawer,
                                         page_nb=page.page_nb)
        scan_workflow.connect('process-done',
                              lambda scan_workflow, img, boxes:
                              GLib.idle_add(self._on_page_ocr_done,
                                            scan_workflow,
                                            img, boxes, page, page_iterator,
                                            docs_done))
        scan_workflow.ocr(page.img, angles=1)

    def _on_page_ocr_done(self, scan_workflow, img, boxes, page, page_iterator,
                          docs_done=None):
        if docs_done is None:
            docs_done = set()
        page.boxes = boxes

        docid = self._main_win.remove_scan_workflow(scan_workflow)

        doc = self._main_win.docsearch.get_doc_from_docid(docid, inst=False)
        docs_done.add(doc)

        try:
            self._do_next_page(page_iterator)
        except StopIteration:
            if self._main_win.doc in docs_done:
                self._main_win.show_doc(self._main_win.doc, force_refresh=True)
            job = self._main_win.job_factories['index_updater'].make(
                self._main_win.docsearch, upd_docs=docs_done, optimize=False)
            self._main_win.schedulers['index'].schedule(job)

    def _do(self):
        SimpleAction.do(self)
        self._do_next_page(self._iterator)

    def do(self, pages_iterator):
        self._iterator = pages_iterator
        if not self.ask_confirmation:
            return self._do()
        ask_confirmation(self._main_win.window, self._do)


class AllPagesIterator(object):
    def __init__(self, docsearch):
        self.__doc_iter = iter(docsearch.docs)
        self.__page_iter = None

    def __iter__(self):
        return self

    def next(self):
        while True:
            try:
                if self.__page_iter is None:
                    raise StopIteration()
                return next(self.__page_iter)
            except StopIteration:
                doc = None
                while doc is None or not doc.has_ocr():
                    doc = next(self.__doc_iter)
                self.__page_iter = iter(doc.pages)

    def __next__(self):
        return self.next()


class ActionRedoAllOCR(ActionRedoOCR):
    def __init__(self, main_window):
        ActionRedoOCR.__init__(self, "Redoing all ocr", main_window)

    def do(self):
        docsearch = self._main_win.docsearch
        all_page_iter = AllPagesIterator(docsearch)
        ActionRedoOCR.do(self, all_page_iter)


class ActionRedoDocOCR(ActionRedoOCR):
    def __init__(self, main_window):
        ActionRedoOCR.__init__(self, "Redoing doc ocr", main_window)

    def do(self):
        doc = self._main_win.doc
        ActionRedoOCR.do(self, iter(doc.pages))


class ActionRedoPageOCR(ActionRedoOCR):
    def __init__(self, main_window):
        ActionRedoOCR.__init__(self, "Redoing page ocr",
                               main_window, ask_confirmation=False)

    def do(self, page=None):
        if page is None:
            page = self._main_win.page
        ActionRedoOCR.do(self, iter([page]))


class BasicActionOpenExportDialog(SimpleAction):
    def __init__(self, main_window, action_txt):
        SimpleAction.__init__(self, action_txt)
        self.main_win = main_window

        self.simplifications = [
            (_("No simplification"), self._noop,),
            # in order of destructiveness
            (_("Grayscale"), self._grayscale,),
            (_("Soft"), self._unpaper,),
            (_("Grayscale + soft"), self._unpaper_grayscale,),
            (_("Black and white"), self._bw),
            (_("Hard"), self._swt_soft,),
            (_("Extreme"), self._swt_hard,),
        ]

    def _noop(self, pil_img):
        return pil_img

    def _bw(self, pil_img):
        pil_img = pil_img.convert("L")  # to grayscale
        pil_img = pil_img.point(lambda x: 0 if x < 128 else 255, '1')
        return pil_img

    def _grayscale(self, pil_img):
        return pil_img.convert("L")

    def _unpaper(self, pil_img):
        # unpaper order
        out_img = pil_img
        out_img = pillowfight.unpaper_blackfilter(out_img)
        out_img = pillowfight.unpaper_noisefilter(out_img)
        out_img = pillowfight.unpaper_blurfilter(out_img)
        out_img = pillowfight.unpaper_masks(out_img)
        out_img = pillowfight.unpaper_grayfilter(out_img)
        out_img = pillowfight.unpaper_border(out_img)
        return out_img

    def _unpaper_grayscale(self, pil_img):
        pil_img = self._grayscale(pil_img)
        pil_img = self._unpaper(pil_img)
        return pil_img

    def _swt_soft(self, pil_img):
        pil_img = pil_img.convert("L")
        return pillowfight.swt(
            pil_img, output_type=pillowfight.SWT_OUTPUT_ORIGINAL_BOXES
        )

    def _swt_hard(self, pil_img):
        pil_img = pil_img.convert("L")
        return pillowfight.swt(
            pil_img, output_type=pillowfight.SWT_OUTPUT_BW_TEXT
        )

    def init_dialog(self):
        widget_tree = load_uifile(os.path.join("mainwindow", "export.glade"))
        self.main_win._hide_export_dialog()
        self.main_win.export['dialog'] = widget_tree.get_object(
            "infobarExport"
        )
        self.main_win.export['fileFormat'] = {
            'widget': widget_tree.get_object("comboboxExportFormat"),
            'model': widget_tree.get_object("liststoreExportFormat"),
        }
        self.main_win.export['pageSimplification'] = {
            'label': widget_tree.get_object("labelPageSimplification"),
            'widget': widget_tree.get_object("comboboxPageSimplification"),
            'model': widget_tree.get_object("liststorePageSimplification"),
        }
        self.main_win.export['pageFormat'] = {
            'label': widget_tree.get_object("labelPageFormat"),
            'widget': widget_tree.get_object("comboboxPageFormat"),
            'model': widget_tree.get_object("liststorePageFormat"),
        }
        self.main_win.export['quality'] = {
            'label': widget_tree.get_object("labelExportQuality"),
            'widget': widget_tree.get_object("scaleQuality"),
            'model': widget_tree.get_object("adjustmentQuality"),
        }
        self.main_win.export['estimated_size'] = \
            widget_tree.get_object("labelEstimatedExportSize")
        self.main_win.export['buttons'] = {
            'ok': widget_tree.get_object("buttonExport"),
            'cancel': widget_tree.get_object("buttonCancelExport"),
        }

        self.main_win.export['estimated_size'].set_text("")

        self.main_win.export['actions'] = {
            'cancel_export': (
                [widget_tree.get_object("buttonCancelExport")],
                ActionCancelExport(self.main_win),
            ),
            'select_export_format': (
                [widget_tree.get_object("comboboxExportFormat")],
                ActionSelectExportFormat(self.main_win),
            ),
            'change_export_property': (
                [
                    widget_tree.get_object("scaleQuality"),
                    widget_tree.get_object("comboboxPageFormat"),
                    widget_tree.get_object("comboboxPageSimplification"),
                ],
                ActionChangeExportProperty(self.main_win),
            ),
            'export': (
                [widget_tree.get_object("buttonExport")],
                ActionExport(self.main_win),
            ),
        }
        connect_actions(self.main_win.export['actions'])

    def open_dialog(self, to_export):
        SimpleAction.do(self)

        self.main_win.export['fileFormat']['model'].clear()
        nb_export_formats = 0
        formats = to_export.get_export_formats()
        logger.info("[Export]: Supported formats: %s" % formats)
        for out_format in to_export.get_export_formats():
            self.main_win.export['fileFormat']['model'].append([out_format])
            nb_export_formats += 1
        self.main_win.export['buttons']['ok'].set_sensitive(
            nb_export_formats >= 1)
        self.main_win.export['fileFormat']['widget'].set_active(0)
        for button in self.main_win.actions['open_view_settings'][0]:
            button.set_sensitive(False)
        self.main_win.drop_boxes()

        self.main_win.export['pageFormat']['model'].clear()
        idx = 0
        default_idx = -1
        for paper_size in Gtk.PaperSize.get_paper_sizes(True):
            store_data = (
                paper_size.get_display_name(),
                paper_size.get_width(Gtk.Unit.POINTS),
                paper_size.get_height(Gtk.Unit.POINTS)
            )
            self.main_win.export['pageFormat']['model'].append(store_data)
            if paper_size.get_name() == paper_size.get_default():
                default_idx = idx
            idx += 1
        if default_idx >= 0:
            widget = self.main_win.export['pageFormat']['widget']
            widget.set_active(default_idx)

        self.main_win.export['pageSimplification']['model'].clear()
        for simplification in self.simplifications:
            self.main_win.export['pageSimplification']['model'].append(
                simplification
            )
        self.main_win.export['pageSimplification']['widget'].set_active(0)

        self.main_win.export['dialog'].show_all()
        self.main_win.global_page_box.add(self.main_win.export['dialog'])
        self.main_win.global_page_box.reorder_child(
            self.main_win.export['dialog'], 0
        )


class MultipleExportTarget(object):
    def __init__(self, doclist):
        self.doclist = []
        for doc in doclist:
            if doc.is_new:
                continue
            self.doclist.append(doc)

    def get_export_formats(self):
        return [_("Multiple PDF in a folder")]

    def build_exporter(self, format, preview_page_nb=0):
        return docexport.MultipleDocExporter(self.doclist)


class ActionOpenExportPageDialog(BasicActionOpenExportDialog):
    def __init__(self, main_window):
        BasicActionOpenExportDialog.__init__(self, main_window,
                                             "Displaying page export dialog")

    def do(self):
        SimpleAction.do(self)
        self.init_dialog()
        self.main_win.export['to_export'] = self.main_win.page
        self.main_win.export['buttons']['ok'].set_label(_("Export page"))
        GLib.idle_add(self.open_dialog, self.main_win.page)


class ActionOpenExportDocDialog(BasicActionOpenExportDialog):
    def __init__(self, main_window):
        BasicActionOpenExportDialog.__init__(self, main_window,
                                             "Displaying page export dialog")

    def do(self):
        SimpleAction.do(self)
        self.init_dialog()
        docs = self.main_win.doclist.get_selected_docs()
        if len(docs) == 0:
            logger.warning("Export: no document selected !?")
            return
        if len(docs) == 1:
            target = docs[0]
            self.main_win.export['buttons']['ok'].set_label(
                _("Export document")
            )
        else:
            target = MultipleExportTarget(docs)
            self.main_win.export['buttons']['ok'].set_label(
                _("Export documents")
            )
            if len(target.doclist) <= 0:
                logger.warning("Export: no valid document to export selected")
                return
        self.main_win.export['to_export'] = target
        GLib.idle_add(self.open_dialog, target)


class ActionSelectExportFormat(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Select export format")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        file_format_widget = self.__main_win.export['fileFormat']['widget']
        format_idx = file_format_widget.get_active()
        if format_idx < 0:
            return
        file_format_model = self.__main_win.export['fileFormat']['model']
        imgformat = file_format_model[format_idx][0]

        target = self.__main_win.export['to_export']
        exporter = target.build_exporter(
            imgformat, self.__main_win.page.page_nb
        )
        self.__main_win.export['exporter'] = exporter

        logger.info("[Export] Format: %s" % (exporter))
        logger.info("[Export] Can change quality ? %s"
                    % exporter.can_change_quality)
        logger.info("[Export] Can select format ? %s"
                    % exporter.can_select_format)

        widgets = [
            (exporter.can_change_quality,
             [
                 self.__main_win.export['quality']['widget'],
                 self.__main_win.export['quality']['label'],
                 self.__main_win.export['pageSimplification']['widget'],
                 self.__main_win.export['pageSimplification']['label'],
             ]),
            (exporter.can_select_format,
             [
                 self.__main_win.export['pageFormat']['widget'],
                 self.__main_win.export['pageFormat']['label'],
             ]),
        ]
        for (sensitive, widgets) in widgets:
            set_widget_state(widgets, sensitive)

        if exporter.can_change_quality or exporter.can_select_format:
            self.__main_win.export['actions']['change_export_property'][1].do()
        else:
            size_txt = sizeof_fmt(exporter.estimate_size())
            self.__main_win.export['estimated_size'].set_text(size_txt)


class ActionChangeExportProperty(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Export property changed")
        self.__main_win = main_window

    def do(self):
        if self.__main_win.export['exporter'] is None:
            # may be triggered when we initialized the export form
            return
        SimpleAction.do(self)

        if self.__main_win.export['exporter'].can_select_format:
            page_format_widget = self.__main_win.export['pageFormat']['widget']
            format_idx = page_format_widget.get_active()
            if (format_idx < 0):
                return
            page_format_model = self.__main_win.export['pageFormat']['model']
            (name, x, y) = page_format_model[format_idx]
            self.__main_win.export['exporter'].set_page_format((x, y))

        if self.__main_win.export['exporter'].can_change_quality:
            quality = self.__main_win.export['quality']['model'].get_value()
            self.__main_win.export['exporter'].set_quality(quality)

            widget = self.__main_win.export['pageSimplification']['widget']
            model = self.__main_win.export['pageSimplification']['model']
            active = widget.get_active()
            if active >= 0:
                (_, simplification_func) = model[widget.get_active()]
                self.__main_win.export['exporter'].set_postprocess_func(
                    simplification_func
                )

        self.__main_win.refresh_export_preview()


class BasicActionEndExport(SimpleAction):
    def __init__(self, main_win, name):
        super().__init__(name)
        self.main_win = main_win


class ActionExport(BasicActionEndExport):
    def __init__(self, main_window):
        super().__init__(main_window, "Export")
        self.main_win = main_window

    def get_path(self):
        mime = self.main_win.export['exporter'].get_mime_type()
        mime = self.main_win.export['exporter'].get_mime_type()
        if mime:
            chooser = Gtk.FileChooserDialog(
                title=_("Save as"),
                transient_for=self.main_win.window,
                action=Gtk.FileChooserAction.SAVE
            )
            file_filter = Gtk.FileFilter()
            file_filter.set_name(str(self.main_win.export['exporter']))
            file_filter.add_mime_type(mime)
            chooser.add_filter(file_filter)
        else:  # directory
            chooser = Gtk.FileChooserDialog(
                title=_("Save in"),
                transient_for=self.main_win.window,
                action=Gtk.FileChooserAction.SELECT_FOLDER
            )

        chooser.add_buttons(Gtk.STOCK_CANCEL,
                            Gtk.ResponseType.CANCEL,
                            Gtk.STOCK_SAVE,
                            Gtk.ResponseType.OK)
        chooser.set_local_only(False)
        response = chooser.run()
        filepath = chooser.get_uri()
        chooser.destroy()
        if response != Gtk.ResponseType.OK:
            logger.warning("File path for export canceled")
            return

        valid_exts = self.main_win.export['exporter'].get_file_extensions()
        if valid_exts:
            for valid_ext in valid_exts:
                if filepath.lower().endswith(valid_ext.lower()):
                    break
            else:
                filepath += ".%s" % valid_exts[0]
        return filepath

    def do(self):
        super().do()
        filepath = self.get_path()
        job = self.main_win.job_factories['export'].make(
            self.main_win.export['exporter'], filepath
        )
        self.main_win.schedulers['export'].schedule(job)
        self.main_win.hide_export_dialog()


class ActionCancelExport(BasicActionEndExport):
    def __init__(self, main_window):
        super().__init__(main_window, "Cancel export")

    def do(self):
        super().do()
        GLib.idle_add(self.main_win.hide_export_dialog)


class ActionOptimizeIndex(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Optimize index")
        self.__main_win = main_window

    def do(self):
        SimpleAction.do(self)
        job = self.__main_win.job_factories['index_updater'].make(
            self.__main_win.docsearch, optimize=True)
        self.__main_win.schedulers['index'].schedule(job)


class ActionOpenDiagnostic(SimpleAction):
    def __init__(self, main_window, libinsane):
        SimpleAction.__init__(self, "Opening diagnostic dialog")
        self.__main_win = main_window
        self.__libinsane = libinsane
        self.diag = None  # used to prevent gc

    def do(self):
        SimpleAction.do(self)
        self.diag = DiagDialog(self.__main_win, self.__libinsane)
        self.diag.show()


class ActionAbout(SimpleAction):
    def __init__(self, main_window):
        SimpleAction.__init__(self, "Opening about dialog")
        self.__main_win = main_window
        self.diag = None  # used to prevent gc

    def do(self):
        SimpleAction.do(self)
        self.diag = AboutDialog(self.__main_win.window)
        self.diag.show()


class ActionQuit(SimpleAction):
    """
    Quit
    """
    def __init__(self, main_window, config):
        SimpleAction.__init__(self, "Quit")
        self.__main_win = main_window
        self.__config = config

    def do(self):
        SimpleAction.do(self)
        self.__main_win.window.destroy()

    def on_window_close_cb(self, window):
        self.do()


class ActionRealQuit(SimpleAction):
    """
    Quit
    """
    def __init__(self, main_window, config, main_loop):
        SimpleAction.__init__(self, "Quit (real)")
        self.__main_win = main_window
        self.__config = config
        self.__main_loop = main_loop

    def do(self):
        SimpleAction.do(self)
        GLib.idle_add(self.__actual_quit)

    def __actual_quit(self):
        # We must stop the schedulers before anything else because jobs
        # may need the Gtk loop or other services to stop correctly
        logger.info("Stopping schedulers ...")
        for scheduler in self.__main_win.schedulers.values():
            scheduler.stop()

        logger.info("Stopping index client ...")
        self.__main_win.docsearch.stop()
        logger.info("Gtk.main_quit() ...")
        self.__main_loop.quit()
        logger.info("Gtk main_loop() interrupted")

    def on_window_close_cb(self, window):
        self.do()


class ActionRefreshIndex(SimpleAction):
    def __init__(self, main_window, config, force=False,
                 skip_examination=False):
        SimpleAction.__init__(self, "Refresh index")
        self.__main_win = main_window
        self.__config = config
        self.__force = force
        self.__connect_handler_id = None
        self.__skip_examination = skip_examination

    def do(self):
        SimpleAction.do(self)
        self.__main_win.schedulers['main'].cancel_all(
            self.__main_win.job_factories['index_reloader'])
        self.__main_win.schedulers['search'].cancel_all(
            self.__main_win.job_factories['doc_examiner'])
        self.__main_win.schedulers['index'].cancel_all(
            self.__main_win.job_factories['index_updater'])
        docsearch = self.__main_win.docsearch
        self.__main_win.docsearch = DummyDocSearch()
        self.__main_win.doclist.clear()
        if not self.__force:
            docsearch.close()
        else:
            docsearch.destroy_index()

        job = self.__main_win.job_factories['index_reloader'].make()
        job.connect('index-loading-end', self.__on_index_reload_end)
        self.__main_win.schedulers['main'].schedule(job)

    def __on_index_reload_end(self, job, docsearch):
        if docsearch is None:
            return
        if self.__skip_examination:
            return
        job = self.__main_win.job_factories['doc_examiner'].make(docsearch)
        job.connect('doc-examination-end', lambda job: GLib.idle_add(
            self.__on_doc_exam_end, job))
        # XXX(Jflesch): Don't lock the main scheduler here
        self.__main_win.schedulers['index'].schedule(job)

    def __on_doc_exam_end(self, examiner):
        logger.info("Document examen finished. Updating index ...")
        logger.info("%d labels found" % len(examiner.labels))
        logger.info("New document: %d" % len(examiner.new_docs))
        logger.info("Updated document: %d" % len(examiner.docs_changed))
        logger.info("Deleted document: %d" % len(examiner.docs_missing))

        examiner.docsearch.label_list = examiner.labels

        if (len(examiner.new_docs) == 0 and
                len(examiner.docs_changed) == 0 and
                len(examiner.docs_missing) == 0):
            logger.info("No changes")
            return

        job = self.__main_win.job_factories['index_updater'].make(
            docsearch=examiner.docsearch,
            new_docs=examiner.new_docs,
            upd_docs=examiner.docs_changed,
            del_docs=examiner.docs_missing,
            reload_list=True,
            optimize=False
        )
        self.__main_win.schedulers['index'].schedule(job)


class ActionOpenHelp(SimpleAction):
    def __init__(self, main_window, help_name):
        super().__init__("Open Help {}".format(help_name))
        self.__main_win = main_window
        self.help_name = help_name

    def do(self):
        super().do()
        docpath = get_documentation(self.help_name)
        docpath = self.__main_win.docsearch.fs.safe(docpath)
        doc = ExternalPdfDoc(self.__main_win.docsearch.fs, docpath)
        self.__main_win.show_page(doc.pages[0], force_refresh=True)
        self.__main_win.doclist.unselect_all()


class ActionNextDocument(SimpleAction):
    def __init__(self, main_window, offset=1):
        super().__init__("Goto next document ({})".format(offset))
        self.__main_win = main_window
        self.offset = offset

    def do(self):
        super().do()
        row = self.__main_win.doclist.select_doc(
            doc=self.__main_win.doc,
            offset=self.offset,
            open_doc=True
        )
        if row is None:
            return
        self.__main_win.doclist.scroll_to(row)


class ActionGotoBox(SimpleAction):
    def __init__(self, main_window, target_page_drawer=None, target_box=None):
        super().__init__("Goto box")
        self.__main_win = main_window
        self.page_drawer = target_page_drawer
        self.box = target_box

    def set_target(self, page_drawer, box):
        self.page_drawer = page_drawer
        self.box = box

    def do(self):
        super().do()

        if self.box is None:
            logger.info("No target box")
            return

        logger.info("Going to p{} box {}".format(
            self.page_drawer, self.box.position
        ))

        self.page_drawer.select_boxes([self.box])

        position = self.page_drawer.get_real_box_position(self.box)[1]
        position -= self.__main_win.img['canvas'].visible_size[1] / 2
        if position < 0:
            position = 0
        logger.info("Position: {}".format(position))
        self.__main_win.img['canvas'].get_vadjustment().set_value(position)
        self.__main_win.searchbar.set_current_box(self.box)


class SearchBar(object):
    def __init__(self, main_win):
        self.__main_win = main_win
        self.boxes = {}
        self.current = None
        self.widget = None
        self.label = None
        self.doc = None
        self.sorted_boxes = []
        self.actions = {}

    def set_visible(self, visible):
        self.boxes = {}

        if (self.widget is not None) == visible:
            return

        if not visible:
            self.widget = None
            self.label = None
            self.boxes = set()
            self.current = None
            self.sorted_boxes = []
            self.actions = {}
            return

        widget_tree = load_uifile(
            os.path.join("mainwindow", "searchbar.glade")
        )

        self.widget = widget_tree.get_object("searchbar")
        self.label = widget_tree.get_object("labelNbSearchResults")

        previous_doc = widget_tree.get_object("buttonPreviousDocument")
        next_doc = widget_tree.get_object("buttonNextDocument")
        first_occ = widget_tree.get_object("buttonFirstOcc")
        last_occ = widget_tree.get_object("buttonLastOcc")
        previous_occ = widget_tree.get_object("buttonPreviousOcc")
        next_occ = widget_tree.get_object("buttonNextOcc")

        self.actions = {
            'next_document':
                ([next_doc], ActionNextDocument(self.__main_win, 1)),
            'previous_document':
                ([previous_doc], ActionNextDocument(self.__main_win, -1)),
            'first_occ': ([first_occ], ActionGotoBox(self.__main_win)),
            'last_occ': ([last_occ], ActionGotoBox(self.__main_win)),
            'previous_occ': ([previous_occ], ActionGotoBox(self.__main_win)),
            'next_occ': ([next_occ], ActionGotoBox(self.__main_win)),
        }
        connect_actions(self.actions)

        accelerators = [
            ('F3', 'clicked', next_occ),
            ('<Shift>F3', 'clicked', previous_occ),
        ]
        accel_group = Gtk.AccelGroup()
        for (shortcut, signame, widget) in accelerators:
            (key, mod) = Gtk.accelerator_parse(shortcut)
            widget.add_accelerator(signame, accel_group, key, mod,
                                   Gtk.AccelFlags.VISIBLE)
        self.__main_win.window.add_accel_group(accel_group)

        self.widget.show_all()
        return

    def is_visible(self):
        return self.widget is not None

    def get_widget(self):
        return self.widget

    def update_boxes(self, page_drawer, boxes):
        if self.widget is None:
            return

        if (self.doc != page_drawer.page.doc):
            # we have switched to another document --> reset known boxes
            self.boxes = {}
            self.current = None
        self.doc = page_drawer.page.doc

        for (position, box) in boxes:
            self.boxes[(page_drawer.page.page_nb, position)] = (
                page_drawer.page.page_nb,
                page_drawer.get_real_box_position(box),
                position,
                page_drawer, box
            )

        self.sorted_boxes = sorted(
            self.boxes.values(),
            # do not sort on the box ref
            key=lambda b: (b[0], b[1][1], b[1][0])
        )

        if len(self.sorted_boxes) <= 0:
            logger.info("No matching boxes in the current document")
            return

        self.set_current_box(self.current)  # update prev/next
        self.actions['first_occ'][1].set_target(
            self.sorted_boxes[0][3], self.sorted_boxes[0][4]
        )
        self.actions['last_occ'][1].set_target(
            self.sorted_boxes[-1][3], self.sorted_boxes[-1][4]
        )

    def set_current_box(self, box):
        if self.widget is None:
            return

        self.current = box
        boxes = [
            b
            for (page_nb, real_position, position, page_d, b)
            in self.sorted_boxes
        ]
        if box is not None and box not in boxes:
            logger.warning("Searchbar: target box is unknown ?!")
            return

        # default
        self.actions['previous_occ'][1].set_target(None, None)
        self.actions['next_occ'][1].set_target(None, None)

        if box is None:
            index = -1
        else:
            index = boxes.index(box)

        if index - 1 >= 0:
            self.actions['previous_occ'][1].set_target(
                self.sorted_boxes[index - 1][3],
                self.sorted_boxes[index - 1][4]
            )
        if index + 1 < len(boxes):
            self.actions['next_occ'][1].set_target(
                self.sorted_boxes[index + 1][3],
                self.sorted_boxes[index + 1][4]
            )

        if index >= 0 and len(self.boxes) > 0:
            index += 1  # human readable
        elif len(self.boxes) > 0:
            index = 1  # human readable
        else:
            index = 0

        self.label.set_text(_("{} of {}").format(
            index, len(self.boxes)
        ))

    def reset(self):
        self.boxes = {}
        self.sorted_boxes = {}
        self.set_current_box(None)


class MainWindow(object):
    def __init__(
            self, config, main_loop, libinsane, workdir_scan=True,
            flatpak=False):
        self.flatpak = flatpak
        self.libinsane = libinsane
        self.ready = False
        self.docsearch = DummyDocSearch()
        self.workdir_scan_at_start = workdir_scan

        self.version = __version__

        if g_must_init_app:
            self.app = self.__init_app()
        else:
            self.app = None
        gactions = self.__init_gactions(self.app)

        self.schedulers = self.__init_schedulers()

        # used by the set_mouse_cursor() function to keep track of how many
        # threads / jobs requested a busy mouse cursor
        self.__busy_mouse_counter = 0

        self.allow_multiselect = False

        self.default_font = None
        load_cssfile("application.css")

        widget_tree = load_uifile(
            os.path.join("mainwindow", "mainwindow.glade"))
        # self.widget_tree is for tests/screenshots ONLY
        self.widget_tree = widget_tree

        self.__init_headerbars(widget_tree)

        self.window = self.__init_window(widget_tree, config)

        self.doclist = DocList(self, config, widget_tree)

        self.__config = config
        self.__scan_start = 0.0
        self.__scan_progress_job = None

        # All the pages are displayed on the canvas,
        # however, only one is the "active one"
        self.doc = self.doclist.get_new_doc()
        self.page = DummyPage(self.doc)
        self.page_drawers = []
        self.layout = "grid"
        self.scan_drawers = {}  # docid --> {page_nb: extra drawer}

        search_completion = Gtk.EntryCompletion()

        self.zoom_level = {
            'gui': widget_tree.get_object("scaleZoom"),
            'model': widget_tree.get_object("adjustmentZoom"),
            'auto': True,  # recomputed if the window size change
        }

        self.lists = {
            'suggestions': {
                'gui': widget_tree.get_object("entrySearch"),
                'completion': search_completion,
                'model': widget_tree.get_object("liststoreSuggestion")
            },
        }

        search_completion.set_model(self.lists['suggestions']['model'])
        search_completion.set_text_column(0)
        search_completion.set_match_func(lambda a, b, c, d: True, None)
        self.lists['suggestions']['completion'] = search_completion
        self.lists['suggestions']['gui'].set_completion(search_completion)

        self.search_field = widget_tree.get_object("entrySearch")

        self.doc_browsing = {
            'search': self.search_field,
        }

        img_scrollbars = widget_tree.get_object("scrolledwindowPageImg")
        img_widget = Canvas(img_scrollbars)
        img_widget.set_visible(True)
        img_scrollbars.add(img_widget)

        img_widget.connect(
            None,
            'window-moved',
            lambda x: GLib.idle_add(self.__on_img_window_moved)
        )

        self.progressbar = ProgressBarDrawer()
        self.progressbar.visible = False
        img_widget.add_drawer(self.progressbar)

        img_widget.connect(
            None,
            'window-moved',
            lambda x: GLib.idle_add(self.__on_img_window_moved)
        )

        self.img = {
            "canvas": img_widget,
            "scrollbar": img_scrollbars,
            "scrollbar_size": (0, 0),
            "viewport": {
                "widget": img_widget,
            },
            "eventbox": widget_tree.get_object("eventboxImg"),
            "pixbuf": None,
            "factor": 1.0,
            "original_width": 1,
            "boxes": {
                'all': [],
                'visible': [],
                'highlighted': [],
                'selected': [],
            }
        }

        self.page_drop_handler = PageDropHandler(self)
        self.img['canvas'].add_drawer(self.page_drop_handler)
        self.page_drop_handler.set_enabled(self.doc.can_edit)

        self.popovers = {
            'view_settings': widget_tree.get_object("view_settings_popover"),
        }

        self.popup_menus = {}

        self.doc_properties_panel = DocPropertiesPanel(self, widget_tree)

        self.headerbars = {
            'left': widget_tree.get_object("headerbar_left"),
            'right': widget_tree.get_object("headerbar_right"),
        }

        self.search_box = widget_tree.get_object("box_search")

        self.left_revealers = {
            'loading': [
                (
                    widget_tree.get_object("box_left_revealers"), 0,
                    widget_tree.get_object("box_left_loading_revealer"),
                ),
                # When loading, do not hide the default headerbar.
                # Users may need it to access diagnostic or settings.
                (
                    widget_tree.get_object("box_headerbar_left"), 0,
                    widget_tree.get_object(
                        "box_headerbar_left_doclist_revealer"
                    ),
                ),
            ],
            'doc_list': [
                (
                    widget_tree.get_object("box_left_revealers"), 1,
                    widget_tree.get_object("box_left_doclist_revealer")
                ),
                (
                    widget_tree.get_object("box_headerbar_left"), 0,
                    widget_tree.get_object(
                        "box_headerbar_left_doclist_revealer"
                    ),
                ),
            ],
            'doc_properties': [
                (
                    widget_tree.get_object("box_left_revealers"), 2,
                    widget_tree.get_object("box_left_docproperties_revealer")
                ),
                (
                    widget_tree.get_object("box_headerbar_left"), 1,
                    widget_tree.get_object(
                        "box_headerbar_left_docproperties_revealer"
                    ),
                ),
            ],
        }

        self.page_nb = {
            'current': widget_tree.get_object("entryPageNb"),
            'total': widget_tree.get_object("labelTotalPages"),
        }

        self.global_page_box = widget_tree.get_object("globalPageBox")
        self.export = {
            'dialog': None,
            'exporter': None,
            'actions': {},
        }

        self.searchbar = SearchBar(self)

        self.layouts = {
            'settings_button': widget_tree.get_object("viewSettingsButton"),
            'grid': {
                'button': widget_tree.get_object("show_grid_button"),
            },
            'paged': {
                'button': widget_tree.get_object("show_paged_button"),
            },
        }

        self.job_factories = {
            'doc_examiner': JobFactoryDocExaminer(self, config),
            'doc_searcher': JobFactoryDocSearcher(self, config),
            'export': JobFactoryExport(self),
            'export_previewer': JobFactoryExportPreviewer(self),
            'img_processer': JobFactoryImgProcesser(self),
            'importer': JobFactoryImporter(self, config),
            'index_reloader': JobFactoryIndexLoader(self, config),
            'index_updater': JobFactoryIndexUpdater(self, config),
            'label_predictor_on_new_doc': JobFactoryLabelPredictorOnNewDoc(
                self
            ),
            'page_img_renderer': JobFactoryPageImgRenderer(self),
            'page_img_loader': JobFactoryPageImgLoader(),
            'page_boxes_loader': JobFactoryPageBoxesLoader(),
        }

        self.actions = {
            'new_doc': (
                [
                    widget_tree.get_object("toolbuttonNewDoc"),
                ],
                ActionNewDocument(self.doclist, self),
            ),
            'open_view_settings': (
                [
                    self.layouts['settings_button'],
                ],
                ActionOpenViewSettings(self),
            ),
            'show_as_grid': (
                [
                    self.layouts['grid']['button'],
                ],
                ActionShowDocumentAsGrid(self)
            ),
            'show_as_paged': (
                [
                    self.layouts['paged']['button'],
                ],
                ActionShowDocumentAsPaged(self)
            ),
            'single_scan': (
                [
                    widget_tree.get_object("buttonScan"),
                ],
                ActionSingleScan(self, config, libinsane)
            ),
            'multi_scan': (
                [
                    gactions['scan_from_feeder'],
                ],
                ActionMultiScan(self, config, libinsane)
            ),
            'import': (
                [
                    gactions['import']
                ],
                ActionImport(self, config)
            ),
            'print': (
                [
                    gactions['print'],
                ],
                ActionPrintDoc(self)
            ),
            'open_export_doc_dialog': (
                [
                    gactions['export_doc'],
                ],
                ActionOpenExportDocDialog(self)
            ),
            'open_export_page_dialog': (
                [
                    gactions['export_page'],
                ],
                ActionOpenExportPageDialog(self)
            ),
            'open_settings': (
                [
                    gactions['open_settings'],
                ],
                ActionOpenSettings(self, config, libinsane)
            ),
            'open_help_introduction': (
                [
                    gactions['open_help_introduction'],
                ],
                ActionOpenHelp(self, "intro")
            ),
            'open_help_manual': (
                [
                    gactions['open_help_manual'],
                ],
                ActionOpenHelp(self, "usage")
            ),
            'quit': (
                [
                    gactions['quit'],
                ],
                ActionQuit(self, config),
            ),
            'open_doc_dir': (
                [
                    gactions['open_doc_dir']
                ],
                ActionOpenDocDir(self),
            ),
            'optimize_index': (
                [
                    gactions['optimize_index'],
                ],
                ActionOptimizeIndex(self),
            ),
            'set_current_page': (
                [
                    self.page_nb['current'],
                ],
                ActionOpenPageNb(self),
            ),
            'zoom_level': (
                [
                    self.zoom_level['model'],
                ],
                ActionUpdPageSizes(self)
            ),
            'search': (
                [
                    self.search_field,
                ],
                ActionUpdateSearchResults(self),
            ),
            'open_search_dialog': (
                [
                    widget_tree.get_object("buttonOpenSearchDialog"),
                ],
                ActionOpenSearchDialog(self),
            ),
            'show_all_boxes': (
                [
                    widget_tree.get_object("show_all_boxes"),
                ],
                ActionToggleAllBoxes(self)
            ),
            'redo_ocr_doc': (
                [
                    gactions['redo_ocr_doc'],
                ],
                ActionRedoDocOCR(self),
            ),
            'redo_ocr_all': (
                [
                    gactions['redo_ocr_all'],
                ],
                ActionRedoAllOCR(self),
            ),
            'reindex_from_scratch': (
                [
                    gactions['reindex_all'],
                ],
                ActionRefreshIndex(self, config, force=True),
            ),
            'reindex': (
                [],
                ActionRefreshIndex(self, config, force=False),
            ),
            'reload': (
                [],
                ActionRefreshIndex(self, config, force=False,
                                   skip_examination=True),
            ),
            'diagnostic': (
                [
                    gactions['diagnostic'],
                ],
                ActionOpenDiagnostic(self, libinsane),
            ),
            'about': (
                [
                    gactions['about'],
                ],
                ActionAbout(self),
            ),
        }

        connect_actions(self.actions)

        accelerators = [
            ('<Primary>n', 'clicked',
             widget_tree.get_object("toolbuttonNewDoc")),
            ('<Primary>f', 'grab-focus',
             self.search_field),
        ]
        accel_group = Gtk.AccelGroup()
        for (shortcut, signame, widget) in accelerators:
            (key, mod) = Gtk.accelerator_parse(shortcut)
            widget.add_accelerator(signame, accel_group, key, mod,
                                   Gtk.AccelFlags.VISIBLE)
        self.window.add_accel_group(accel_group)

        self.window.add_events(Gdk.EventMask.KEY_PRESS_MASK)

        self.need_doc_widgets = set(
            self.actions['print'][0] +
            self.actions['open_doc_dir'][0] +
            self.actions['redo_ocr_doc'][0] +
            self.actions['open_export_doc_dialog'][0] +
            self.actions['set_current_page'][0] +
            self.actions['open_view_settings'][0]
        )

        self.need_page_widgets = set(
            self.actions['open_export_page_dialog'][0]
        )

        self.__show_all_boxes_widget = \
            self.actions['show_all_boxes'][0][0]

        set_widget_state(self.need_page_widgets, False)
        set_widget_state(self.need_doc_widgets, False)
        set_widget_state(
            self.actions['multi_scan'][0],
            self.__config['scanner_has_feeder'].value
        )

        for (popup_menu_name, popup_menu) in self.popup_menus.items():
            assert(not popup_menu[0] is None)
            assert(not popup_menu[1] is None)
            # TODO(Jflesch): Find the correct signal
            # This one doesn't take into account the key to access these menus
            popup_menu[0].connect("button-press-event", self.__popup_menu_cb,
                                  popup_menu[0], popup_menu[1])

        self.window.connect(
            "destroy",
            ActionRealQuit(self, config, main_loop).on_window_close_cb
        )

        self.img['scrollbar'].connect("size-allocate",
                                      self.__on_img_area_resize_cb)
        self.window.connect("size-allocate", self.__on_window_resized_cb)

        self.img['canvas'].connect(
            None, "scroll-event", self.__on_scroll_event_cb
        )
        self.window.connect(
            "key-press-event", self.__on_key_press_event_cb,
        )
        self.window.connect(
            "key-release-event", self.__on_key_release_event_cb,
        )
        self.window.connect("realize", self.__on_window_realize_cb)

        for scheduler in self.schedulers.values():
            scheduler.start()

        GLib.idle_add(self.__init_canvas, config)
        GLib.idle_add(self.window.set_visible, True)

        self.beacon = beacon.Beacon(config, flatpak)
        beacon.check_update(self.beacon)

    def __init_headerbars(self, widget_tree):
        # Fix Unity placement of close/minize/maximize (it *must* be on the
        # right)

        try:
            left = "menu"
            right = "close"

            settings = Gtk.Settings.get_default()
            default_layout = settings.get_property("gtk-decoration-layout")
            if "maximize" in default_layout:
                right = "maximize," + right
            if "minimize" in default_layout:
                right = "minimize," + right

            # disable global setting for decoration
            settings.set_property("gtk-decoration-layout", ":close")

            # and use local ones only
            widget_tree.get_object(
                "doclist_headerbar_left"
            ).set_decoration_layout(left + ":")
            widget_tree.get_object(
                "headerbar_right"
            ).set_decoration_layout(":" + right)
        except TypeError as exc:
            # gtk-decoration-layout only appeared in Gtk >= 3.12
            # Some distribution still have Gtk-3.10 at this time
            # (Linux Mint 17 for instance)
            logger.warning(
                "Exception while configuring GTK decorations: %s: %s"
                % (str(type(exc)), str(exc))
            )
            logger.exception(exc)

        widget_tree.get_object("labelTotalPages").set_size_request(1, 30)
        widget_tree.get_object("entryPageNb").set_size_request(1, 30)
        widget_tree.get_object("viewSettingsButton").set_size_request(1, 30)

    def __init_app(self):
        if hasattr(GLib, 'set_application_name'):
            GLib.set_application_name(_("Paperwork"))
        GLib.set_prgname("paperwork")

        app = Gtk.Application(
            application_id=None,
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        app.register(None)
        Gtk.Application.set_default(app)
        return app

    def __init_gactions(self, app):
        gactions = {
            'about': Gio.SimpleAction.new("about", None),
            'diagnostic': Gio.SimpleAction.new("diag", None),
            'export_doc': Gio.SimpleAction.new("export_doc", None),
            'export_page': Gio.SimpleAction.new("export_page", None),
            'import': Gio.SimpleAction.new("import", None),
            'open_help_introduction': Gio.SimpleAction.new("help.introduction",
                                                           None),
            'open_help_manual': Gio.SimpleAction.new("help.manual", None),
            'open_settings': Gio.SimpleAction.new("settings", None),
            'open_doc_dir': Gio.SimpleAction.new("doc_open_dir", None),
            'optimize_index': Gio.SimpleAction.new("optimize_index", None),
            'print': Gio.SimpleAction.new("print", None),
            'redo_ocr_doc': Gio.SimpleAction.new("redo_ocr_doc", None),
            'redo_ocr_all': Gio.SimpleAction.new("redo_ocr_all", None),
            'reindex_all': Gio.SimpleAction.new("reindex_all", None),
            'scan_single': Gio.SimpleAction.new("scan_single_page", None),
            'scan_from_feeder': Gio.SimpleAction.new("scan_from_feeder", None),
            'quit': Gio.SimpleAction.new("quit", None),
        }
        if g_must_init_app:
            for action in gactions.values():
                app.add_action(action)
        return gactions

    def __init_schedulers(self):
        return {
            'main': JobScheduler("Main"),
            'search': JobScheduler('Search'),
            'ocr': JobScheduler("OCR"),
            'page_boxes_loader': JobScheduler("Page boxes loader"),
            'progress': JobScheduler("Progress"),
            'scan': JobScheduler("Scan"),
            'index': JobScheduler("Index search / update"),
            'export': JobScheduler("Export"),
        }

    def __init_window(self, widget_tree, config):
        window = widget_tree.get_object("mainWindow")
        if g_must_init_app:
            window.set_application(self.app)
        window.set_default_size(config['main_win_size'].value[0],
                                config['main_win_size'].value[1])

        # before loading the main window, load the icon, so Gtk can access
        # it too
        logo_path = preload_file("paperwork_halo.svg")
        logo = GdkPixbuf.Pixbuf.new_from_file(logo_path)
        window.set_icon(logo)
        return window

    def __init_canvas(self, config):
        logo = "paperwork_100.png"
        pkg = "paperwork.frontend.data"

        logo_size = (0, 0)
        try:
            logo = load_image(logo, pkg=pkg)
            logo_size = logo.size
            logo_drawer = PillowImageDrawer((
                - (logo_size[0] / 2),
                - (logo_size[1] / 2) - 12,
            ), logo)
            logo_drawer = Centerer(logo_drawer)
            logo_drawer.layer = logo_drawer.BACKGROUND_LAYER
            self.img['canvas'].add_drawer(logo_drawer)
        except Exception as exc:
            logger.warning("Failed to display logo: {}".format(exc))
            raise

        update = config['last_update_found'].value
        version = self.version.split("-")[0]

        lines = [
            ("Paperwork {}".format(__version__), 28),
        ]
        if update and update != version:
            lines += [
                (_("A new version is available:"), 20),
                (_("Paperwork {}").format(update), 20),
                # TODO(Jflesch): Make that a link
                ("https://openpaper.work/download/", 20),
            ]

        pos = logo_size[1] / 2
        for (txt, font_size) in lines:
            txt_drawer = TextDrawer((0, pos), txt, height=font_size)
            txt_drawer.font = self.default_font
            txt_drawer = Centerer(txt_drawer)
            self.img['canvas'].add_drawer(txt_drawer)
            pos += font_size + 5

    def set_search_availability(self, enabled):
        set_widget_state(self.doc_browsing.values(), enabled)

    def set_mouse_cursor(self, cursor):
        offset = {
            "Normal": -1,
            "Busy": 1
        }[cursor]

        self.__busy_mouse_counter += offset
        assert(self.__busy_mouse_counter >= 0)

        if self.__busy_mouse_counter > 0:
            display = self.window.get_display()
            cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.WATCH)
        else:
            cursor = None
        self.window.get_window().set_cursor(cursor)

    def set_progression(self, src, progression, text):
        if progression > 0.0 or text is not None:
            self.progressbar.visible = True
            self.progressbar.set_progression(100 * progression, text)
        else:
            self.progressbar.visible = False
        self.progressbar.redraw()

    def new_doc(self):
        self.actions['new_doc'][1].do()

    def set_zoom_level(self, level, auto=False):
        logger.info("Changing zoom level (internal): {}/{}".format(
            auto, level
        ))
        self.actions['zoom_level'][1].enabled = False
        self.zoom_level['model'].set_value(level)
        self.zoom_level['auto'] = auto
        self.actions['zoom_level'][1].enabled = True

    def on_index_loading_start_cb(self, src):
        self.set_progression(src, 0.0, None)
        self.set_search_availability(False)
        self.set_mouse_cursor("Busy")

    def on_index_loading_end_cb(self, src, docsearch):
        logger.info("Index loaded")

        self.ready = True

        self.set_progression(src, 0.0, None)
        self.set_search_availability(True)
        self.set_mouse_cursor("Normal")

        if docsearch is None:
            return

        beacon.send_statistics(self.beacon, self.version, docsearch)

        self.docsearch = docsearch
        self.refresh_doc_list()
        self.refresh_label_list()

        GLib.timeout_add(1000, self._check_new_workdir)

    def _check_new_workdir(self):
        if self.docsearch.nb_docs > 0:
            return

        def set_labels(doc, labels):
            doc.labels = labels
            self.upd_index({doc})
            GLib.idle_add(self.doclist.select_doc, doc)

        # no document --> add the introduction document
        docpath = get_documentation('intro')
        docuri = fs.GioFileSystem().safe(docpath)
        importers = docimport.get_possible_importers([docuri], self.doc)
        job_importer = self.job_factories['importer']
        job_importer = job_importer.make(importers[0], [docuri])

        label = Label(name=_("Documentation"), color="#ffffffffffff")
        job_importer.connect(
            'import-ok',
            lambda _, stats, doc, uris: GLib.idle_add(
                set_labels, doc, [label]
            )
        )
        self.schedulers['main'].schedule(job_importer)

    def on_doc_examination_start_cb(self, src):
        self.set_progression(src, 0.0, None)

    def on_doc_examination_end_cb(self, src):
        self.set_progression(src, 0.0, None)

    def on_index_update_start_cb(self, src):
        self.doclist.show_loading()
        self.set_progression(src, 0.0, None)

    def on_index_update_write_cb(self, src):
        if src.update_only:
            self.doclist.refresh()

    def on_index_update_end_cb(self, src):
        self.schedulers['main'].cancel_all(
            self.job_factories['index_reloader'])

        self.set_progression(src, 0.0, None)
        gc.collect()
        self.doclist.refresh()

    def on_search_start_cb(self, search):
        self.search_field.override_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(red=0.50, green=0.50, blue=0.50, alpha=1.0)
        )
        self.set_searchbar_visible(search != u"")

    def on_search_invalid_cb(self):
        self.schedulers['main'].cancel_all(
            self.doclist.job_factories['doc_thumbnailer'])
        self.search_field.override_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(red=1.0, green=0.0, blue=0.0, alpha=1.0)
        )
        self.doclist.clear()

    def switch_leftpane(self, to):
        all_revealers = {}

        for (name, revealers) in self.left_revealers.items():
            must_be_visible = (to == name)
            for (parent, position, revealer) in revealers:
                # Some revealers are used in many cases. If one of the cases
                # is the target, then the revealer must be visible. If none
                # of the cases of the revealer is the target, then only
                # it must be invisible.
                if revealer in all_revealers and not must_be_visible:
                    continue
                all_revealers[revealer] = (parent, position, must_be_visible)

        for (revealer, (parent, position, must_be_visible)) \
                in all_revealers.items():
            if parent is not None:
                is_visible = revealer in parent.get_children()
                if must_be_visible and not is_visible:
                    parent.add(revealer)
                elif not must_be_visible and is_visible:
                    # WORKAROUND(Jflesch):
                    # We remove the GtkRevealers. It reduces the amount
                    # of warnings of Gtk about GtkRevealers size
                    # and it forces a redraw avoiding some other issues.
                    # Remove only after transition
                    if os.name == "nt":
                        parent.remove(revealer)
                    else:
                        GLib.timeout_add(500, parent.remove, revealer)
                if must_be_visible:
                    parent.reorder_child(revealer, position)
            revealer.set_reveal_child(must_be_visible)

        self.search_box.set_visible(to != 'doc_properties')

    def on_search_results_cb(self, search, documents):
        logger.info("Got {} documents".format(len(documents)))
        self.search_field.override_color(Gtk.StateFlags.NORMAL, None)
        self.doclist.set_docs(
            documents,
            all_docs=(search.strip() == u"")
        )

    def on_search_suggestions_cb(self, suggestions):
        logger.info("Got {} suggestions".format(len(suggestions)))
        self.lists['suggestions']['gui'].freeze_child_notify()
        try:
            self.lists['suggestions']['model'].clear()
            for suggestion in suggestions:
                self.lists['suggestions']['model'].append([suggestion])
        finally:
            self.lists['suggestions']['gui'].thaw_child_notify()
        GLib.idle_add(self.lists['suggestions']['completion'].complete)

    def drop_boxes(self):
        self.img['boxes']['all'] = []
        self.img['boxes']['highlighted'] = []
        self.img['boxes']['visible'] = []

    def on_redo_ocr_end_cb(self, src):
        pass

    def __popup_menu_cb(self, ev_component, event, ui_component, popup_menu):
        if (not event.triggers_context_menu() or
                event.type != Gdk.EventType.BUTTON_PRESS):
            return
        popup_menu.popup(None, None, None, None, event.button, event.time)

    def refresh_docs(self, docs, redo_thumbnails=True):
        self.doclist.refresh_docs(docs, redo_thumbnails)

    def refresh_doc_list(self):
        self.doclist.refresh()

    def refresh_boxes(self):
        search = self.search_field.get_text()
        for page in self.page_drawers:
            if hasattr(page, 'reload_boxes'):
                page.show_all_boxes = self.show_all_boxes
                page.reload_boxes(search)

    def update_page_sizes(self):
        (auto, factor) = self.get_zoom_level()
        # apply the computed factor to the widget managing the zoom level
        self.set_zoom_level(factor, auto)

        self.schedulers['main'].cancel_all(
            self.job_factories['page_img_loader']
        )
        self.schedulers['main'].cancel_all(
            self.job_factories['page_boxes_loader']
        )

        for page in self.page_drawers:
            page.set_size_ratio(factor)
            page.relocate()
        if self.doc.docid in self.scan_drawers:
            for drawer in self.scan_drawers[self.doc.docid].values():
                drawer.relocate()

    def set_layout(self, layout, force_refresh=True):
        if self.layout == layout:
            return
        self.layout = layout
        if force_refresh and self.doc is not None:
            self.show_doc(self.doc, force_refresh=True)
        img = {
            'grid': Gtk.Image.new_from_icon_name("view-grid-symbolic",
                                                 Gtk.IconSize.MENU),
            'paged': Gtk.Image.new_from_icon_name("view-paged-symbolic",
                                                  Gtk.IconSize.MENU),
        }[layout]
        self.layouts['settings_button'].set_image(img)

    def __reset_page_drawers(self, doc):
        self.schedulers['main'].cancel_all(
            self.job_factories['page_img_loader']
        )
        self.schedulers['main'].cancel_all(
            self.job_factories['page_boxes_loader']
        )

        self.img['canvas'].remove_all_drawers()
        self.img['canvas'].add_drawer(self.progressbar)
        assert(self.progressbar.canvas)

        factories = {
            'img_processer': self.job_factories['img_processer'],
            'page_img_loader': self.job_factories['page_img_loader'],
            'page_boxes_loader': self.job_factories['page_boxes_loader']
        }
        schedulers = {
            'page_img_loader': self.schedulers['main'],
            'page_boxes_loader': self.schedulers['page_boxes_loader'],
        }

        self.page_drawers = []
        scan_drawers = {}
        if self.doc.docid in self.scan_drawers:
            scan_drawers = dict(self.scan_drawers[self.doc.docid])

        search = self.search_field.get_text()

        previous_drawer = None
        first_scan_drawer = None
        for page in doc.pages:
            if page.page_nb in scan_drawers:
                # scan drawers on existing pages ("redo OCR", etc)
                drawer = scan_drawers.pop(page.page_nb)
                drawer.previous_drawer = previous_drawer
                drawer.relocate()
                if not first_scan_drawer:
                    first_scan_drawer = drawer
            else:
                # normal pages
                drawer = PageDrawer(page, factories, schedulers,
                                    previous_drawer,
                                    show_boxes=(self.layout == 'paged'),
                                    show_border=(self.layout == 'grid'),
                                    show_all_boxes=self.show_all_boxes,
                                    enable_editor=(self.layout == 'paged'),
                                    sentence=search)
                drawer.connect("page-selected", self._on_page_drawer_selected)
                drawer.connect("page-edited", self._on_page_drawer_edited)
                drawer.connect("may-need-resize",
                               self._on_page_drawer_need_resize)
                drawer.connect("page-deleted", self._on_page_drawer_deleted)
                drawer.connect("page-matching-boxes",
                               self._on_page_matching_boxes)
            previous_drawer = drawer
            self.page_drawers.append(drawer)
            self.img['canvas'].add_drawer(drawer)

        for (page_nb, drawer) in scan_drawers.items():
            # remaining scan drawers ("scan new page", etc)
            drawer.previous_drawer = previous_drawer
            drawer.relocate()
            logger.info("Scan/OCR drawer {} : {} - {}".format(
                page_nb, drawer.position, drawer.size
            ))
            self.page_drawers.append(drawer)
            self.img['canvas'].add_drawer(drawer)
            previous_drawer = drawer
            if not first_scan_drawer:
                first_scan_drawer = drawer

        return first_scan_drawer

    def _hide_export_dialog(self):
        if self.export['dialog'] is not None:
            self.global_page_box.remove(self.export['dialog'])
            self.export['dialog'].set_visible(False)
        self.export['dialog'] = None
        self.export['exporter'] = None
        for button in self.actions['open_view_settings'][0]:
            button.set_sensitive(True)

    def set_searchbar_visible(self, visible):
        if self.searchbar.is_visible() == visible:
            return

        if not visible:
            if self.searchbar.get_widget():
                self.global_page_box.remove(self.searchbar.get_widget())

        self.searchbar.set_visible(visible)

        if visible:
            self.global_page_box.add(self.searchbar.get_widget())
            self.global_page_box.reorder_child(self.searchbar.get_widget(), 0)

    def _update_selection_in_doclist(self, doc, force_refresh):
        if self.allow_multiselect:
            if doc.is_new:
                logger.info("Selecting \"New document\" with other documents"
                            " isn't allowed")
                self.doclist.unselect_doc(doc)
                return (False, force_refresh)
            if self.doc is not None and self.doc == doc:
                logger.info("Unselecting {}".format(doc))
                self.doclist.unselect_doc(doc)
                doc = self.doclist.get_closest_selected_doc(doc)
                if not doc:
                    return (False, force_refresh)
            # Make sure the new document is not selected
            self.doclist.unselect_doc(self.doclist.new_doc)
        elif self.doclist.has_multiselect():
            # current selection isn't valid anymore
            force_refresh = True

        if not self.allow_multiselect:
            self.doclist.select_doc(doc, open_doc=False)

        if (self.doc is not None and
                self.doc == doc and
                not force_refresh):
            logger.info("Doc is already shown")
            return (True, force_refresh)

        return (True, force_refresh)

    def _show_pages(self, doc):
        if not self.page or self.page.doc.docid != doc.docid:
            if doc.nb_pages > 0:
                self.page = self.doc.pages[0]
            else:
                self.page = None

        first_scan_drawer = self.__reset_page_drawers(doc)

        # reset zoom level
        self.set_zoom_level(1.0, auto=True)
        self.update_page_sizes()
        self.img['canvas'].recompute_size(upd_scrollbar_values=False)

        if first_scan_drawer:
            # focus on the activity
            self.img['canvas'].get_vadjustment().set_value(
                first_scan_drawer.position[1]
            )
        else:
            self.img['canvas'].get_vadjustment().set_value(0)

        if self.doc.can_edit:
            self.img['canvas'].add_drawer(self.page_drop_handler)
        self.page_drop_handler.set_enabled(self.doc.can_edit)

    def _show_doc_internal(self, doc, force_refresh=False):
        # Make sure we display the same instance of the document than the
        # one in the backend. Not a copy (unless there is no instance in the
        # backend)
        # This is required to workaround some issues regarding caching
        # in the backend
        doc_inst = self.docsearch.get_doc_from_docid(doc.docid, inst=False)
        if doc_inst:
            doc = doc_inst

        # make sure the export dialog didn't screw up
        for button in self.actions['open_view_settings'][0]:
            button.set_sensitive(True)

        self._hide_export_dialog()
        self.searchbar.reset()

        (changed, force_refresh) = self._update_selection_in_doclist(
            doc, force_refresh
        )
        if not changed:
            return

        logger.info("Showing document {}".format(doc))

        gc.collect()

        self.doc = doc
        self.refresh_header_bar()
        self._show_pages(doc)

        is_new = doc.is_new
        can_edit = doc.can_edit

        set_widget_state(self.need_doc_widgets, not is_new)
        set_widget_state(self.need_page_widgets,
                         not is_new and self.layout == 'paged')
        set_widget_state(self.actions['single_scan'][0], can_edit)

        self.doclist.set_selected_doc(self.doc)
        self.doc_properties_panel.set_doc(self.doc)

    def _show_doc_hook(self, doc, force_refresh=False):
        try:
            self._show_doc_internal(doc, force_refresh)
        finally:
            self.set_mouse_cursor("Normal")

    def show_doc(self, doc, force_refresh=False):
        self.set_mouse_cursor("Busy")
        GLib.idle_add(self._show_doc_hook, doc, force_refresh)

    def refresh_header_bar(self):
        # Pages
        page = self.page
        self.__select_page(page)
        self.page_nb['total'].set_text(_("/ %d") % (self.doc.nb_pages))

        # Title
        self.headerbars['right'].set_title(self.doc.name)

    def _show_page_internal(self, page, force_refresh=False):
        if page is None:
            return

        logger.info("Showing page %s" % page)
        self.page = page

        if (page.doc != self.doc or force_refresh):
            self.set_layout('paged', force_refresh=False)
            self._show_doc_internal(page.doc, force_refresh)

        if self.export['dialog']:
            self.hide_export_dialog()

        drawer = None
        for d in self.page_drawers:
            if d.page == page:
                drawer = d
                break

        if drawer is not None:
            self.img['canvas'].get_vadjustment().set_value(
                drawer.position[1] - SimplePageDrawer.MARGIN
            )

        if self.export['exporter'] is not None:
            logger.info("Canceling export")
            self.export['actions']['cancel_export'][1].do()

        set_widget_state(self.need_page_widgets, self.layout == 'paged')
        self.img['canvas'].redraw()

        self.refresh_header_bar()

    def _show_page_hook(self, page, force_refresh=False):
        try:
            self._show_page_internal(page, force_refresh)
        finally:
            self.set_mouse_cursor("Normal")

    def show_page(self, page, force_refresh=False):
        self.set_mouse_cursor("Busy")
        GLib.idle_add(self._show_page_hook, page, force_refresh)

    def _on_img_processing_start(self):
        self.set_mouse_cursor("Busy")

    def _on_img_processing_done(self):
        self.set_mouse_cursor("Normal")

    def _on_page_drawer_selected(self, page_drawer):
        if self.layout == 'paged':
            return
        self.set_layout('paged', force_refresh=False)
        self.show_page(page_drawer.page, force_refresh=True)

    def _on_page_drawer_edited(self, page_drawer, actions):
        img = None
        for action in actions:
            img = action.apply(img)
        page = page_drawer.page
        page.img = img  # will save the new image

        ActionRedoPageOCR(self).do(page)
        self.refresh_docs([page.doc])

    def __on_page_drawer_need_resize(self, page_drawer):
        self.update_page_sizes()
        self.img['canvas'].recompute_size(upd_scrollbar_values=False)
        self.img['canvas'].redraw()

    def _on_page_drawer_need_resize(self, page_drawer):
        GLib.idle_add(self.__on_page_drawer_need_resize, page_drawer)

    def _on_page_drawer_deleted(self, page_drawer):
        ActionDeletePage(self).do(page_drawer.page)

    def _on_page_matching_boxes(self, page_drawer, boxes):
        self.searchbar.update_boxes(page_drawer, boxes)

    def refresh_label_list(self):
        # make sure the correct doc is taken into account
        self.doc_properties_panel.set_doc(self.doc)

    def on_export_preview_start(self):
        visible = self.img['canvas'].visible_size
        spinner = SpinnerAnimation(
            ((visible[0] - SpinnerAnimation.ICON_SIZE) / 2,
             (visible[1] - SpinnerAnimation.ICON_SIZE) / 2)
        )

        self.img['canvas'].add_drawer(spinner)
        self.export['estimated_size'].set_text(_("Computing ..."))

    def on_export_preview_done(self, img_size, drawer):
        self.img['canvas'].remove_all_drawers()
        self.img['canvas'].add_drawer(self.progressbar)
        self.img['canvas'].add_drawer(drawer)

        self.export['estimated_size'].set_text(sizeof_fmt(img_size))

    def __get_img_area_width(self):
        w = self.img['viewport']['widget'].get_allocation().width
        w -= 2 * SimplePageDrawer.MARGIN
        return w

    def __get_img_area_height(self):
        h = self.img['viewport']['widget'].get_allocation().height
        h -= 2 * SimplePageDrawer.MARGIN
        return h

    def get_zoom_level(self):
        auto = self.zoom_level['auto']
        if auto:
            # compute the wanted factor
            factor = 1.0
            for page in self.page_drawers:
                others = [
                    drawer.page for drawer in self.page_drawers
                    if drawer.page
                ]
                factor = min(factor, self.compute_zoom_level(
                    page.max_size, others))
        else:
            factor = self.zoom_level['model'].get_value()
        return (auto, factor)

    def compute_zoom_level(self, img_size, other_pages):
        if self.layout == "grid":
            # see if we could fit all the pages on one line
            total_width = sum([page.size[0] for page in other_pages])
            canvas_width = self.img['canvas'].visible_size[0]
            canvas_width -= len(other_pages) * (2 * SimplePageDrawer.MARGIN)
            if total_width > 0:
                factor = (float(canvas_width) / float(total_width))
            else:
                factor = 1
            expected_width = img_size[0] * factor
            expected_height = img_size[0] * factor
            if (expected_width > BasicPage.DEFAULT_THUMB_WIDTH and
                    expected_height > BasicPage.DEFAULT_THUMB_HEIGHT):
                return factor

            # otherwise, fall back on the default size
            wanted_height = BasicPage.DEFAULT_THUMB_HEIGHT
            return float(wanted_height) / img_size[1]
        else:
            auto = self.zoom_level['auto']
            factor = self.zoom_level['model'].get_value()
            # factor is a postive float if user defined, 0 for full width and
            # -1 for full page
            if not auto:
                return factor
            wanted_width = self.__get_img_area_width()
            width_factor = float(wanted_width) / img_size[0]
            if factor == -1.0:
                wanted_height = self.__get_img_area_height()
                factor = min(width_factor, float(wanted_height) / img_size[1])
                return factor
            else:
                return width_factor

    def refresh_export_preview(self):
        self.img['canvas'].remove_all_drawers()
        self.img['canvas'].add_drawer(self.progressbar)
        self.schedulers['main'].cancel_all(
            self.job_factories['export_previewer']
        )
        job = self.job_factories['export_previewer'].make(
            self.export['exporter'])
        self.schedulers['main'].schedule(job)

    def __on_img_area_resize_cb(self, scrollbar, rectangle):
        if self.export['exporter'] is not None:
            return

        old_size = self.img['scrollbar_size']
        new_size = (rectangle.width, rectangle.height)
        if old_size == new_size:
            return

        logger.info("Image view port resized. (%d, %d) --> (%d, %d)"
                    % (old_size[0], old_size[1], new_size[0], new_size[1]))
        self.img['scrollbar_size'] = new_size

        (auto, factor) = self.get_zoom_level()
        if not auto:
            return

        self.update_page_sizes()
        self.img['canvas'].recompute_size(upd_scrollbar_values=True)
        self.img['canvas'].redraw(checked=True)

    def __on_doc_lines_shown(self, docs):
        job = self.job_factories['doc_thumbnailer'].make(docs)
        self.schedulers['main'].schedule(job)

    def __on_window_resized_cb(self, w, rectangle):
        (w, h) = w.get_size()
        self.__config['main_win_size'].value = (w, h)

    def __on_window_realize_cb(self, _):
        action = 'reindex' if self.workdir_scan_at_start else 'reload'
        self.workdir_scan_at_start = False
        GLib.idle_add(self.actions[action][1].do)

    def __set_zoom_level_on_scroll(self, zoom):
        logger.info("Changing zoom level (scroll): %f"
                    % zoom)
        self.set_zoom_level(zoom, auto=False)
        self.update_page_sizes()
        self.img['canvas'].recompute_size(upd_scrollbar_values=True)
        self.img['canvas'].redraw()

    ZOOM_INCREMENT = 0.02

    def __on_scroll_event_cb(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            zoom_model = self.zoom_level['model']
            zoom = zoom_model.get_value()
            if event.direction == Gdk.ScrollDirection.UP:
                zoom += self.ZOOM_INCREMENT
            elif event.direction == Gdk.ScrollDirection.DOWN:
                zoom -= self.ZOOM_INCREMENT
            else:
                return False
            GLib.idle_add(self.__set_zoom_level_on_scroll, zoom)
            return True
        # don't know what to do, don't care. Let someone else take care of it
        return False

    def __on_key_press_event_cb(self, widget, event):
        direction = 0
        if event.keyval == Gdk.KEY_Page_Up:
            direction = -1
        elif event.keyval == Gdk.KEY_Page_Down:
            direction = 1

        if direction != 0:
            logger.info("Direction key pressed (page up / page down)")
            if not event.state & Gdk.ModifierType.CONTROL_MASK:
                logger.info("Changing page (key PageUp/PageDown)")
                doc = self.doc
                if not self.page:
                    page_nb = doc.nb_pages - 1
                else:
                    page_nb = self.page.page_nb
                page_nb += direction
                if page_nb >= doc.nb_pages:
                    page_nb = doc.nb_pages - 1
                if page_nb < 0:
                    page_nb = 0
                self.show_page(doc.pages[page_nb])
            else:
                logger.info("Changing document (keys Ctrl+PageUp/PageDown)")
                row = self.doclist.select_doc(
                    doc=self.doc,
                    offset=direction, open_doc=True
                )
                self.doclist.scroll_to(row)
            return True

        # don't know what to do, don't care. Let someone else take care of it
        return False

    def __on_key_release_event_cb(self, widget, event):
        pass

    def get_doc_sorting(self):
        return ("scan_date", sort_documents_by_date)

    def __get_show_all_boxes(self):
        return self.__show_all_boxes_widget.get_active()

    def __set_show_all_boxes(self, value):
        self.__show_all_boxes_widget.set_active(bool(value))

    show_all_boxes = property(__get_show_all_boxes, __set_show_all_boxes)

    def __select_page(self, page):
        self.page = page
        set_widget_state(self.need_page_widgets, self.layout == 'paged')
        if page:
            new_text = "%d" % (page.page_nb + 1)
        else:
            new_text = ""
        current_text = self.page_nb['current'].get_text()
        if new_text.strip() != current_text.strip():
            self.actions['set_current_page'][1].enabled = False
            self.page_nb['current'].set_text(new_text)
            self.actions['set_current_page'][1].enabled = True

    def __on_img_window_moved(self):
        pos = self.img['canvas'].position
        size = self.img['canvas'].visible_size
        pos = (pos[0] + (size[0] / 2),
               pos[1] + (size[1] / 2))
        drawer = self.img['canvas'].get_drawer_at(pos)
        if drawer is None:
            return
        if not hasattr(drawer, 'page'):
            return
        page = drawer.page
        if page is None:
            set_widget_state(self.need_page_widgets, False)
            return
        self.__select_page(page)

    def make_scan_workflow(self, multiple=False):
        return ScanWorkflow(self.__config,
                            self.schedulers['scan'],
                            self.schedulers['ocr'],
                            multiple)

    def make_scan_workflow_drawer(self, scan_workflow, single_angle=False,
                                  page=None):
        if single_angle:
            drawer = SingleAngleScanWorkflowDrawer(scan_workflow, page)
        else:
            drawer = MultiAnglesScanWorkflowDrawer(scan_workflow, page)
        # make sure the canvas is set even if we don't display it
        drawer.set_canvas(self.img['canvas'])
        return drawer

    def remove_scan_workflow(self, scan_workflow):
        for (docid, drawers) in self.scan_drawers.items():
            for (page_nb, drawer) in drawers.items():
                if (scan_workflow == drawer or
                        scan_workflow == drawer.scan_workflow):
                    drawers.pop(page_nb)
                    return docid
        raise ValueError("ScanWorkflow not found")

    def add_scan_workflow(self, doc, scan_workflow_drawer, page_nb=-1):
        if doc.docid not in self.scan_drawers:
            self.scan_drawers[doc.docid] = {}
        if page_nb < 0:
            page_nb = doc.nb_pages
            while page_nb in self.scan_drawers[doc.docid]:
                page_nb += 1
        self.scan_drawers[doc.docid][page_nb] = scan_workflow_drawer

        if (self.doc.docid == doc.docid or
                (self.doc.is_new and doc.is_new)):
            self.page = None
            set_widget_state(self.need_page_widgets, False)
            self.show_doc(self.doc, force_refresh=True)

    def add_page(self, docid, img, line_boxes):
        doc = self.docsearch.get_doc_from_docid(docid, inst=False)

        new = False
        if doc is None or doc.nb_pages <= 0 or doc.is_new:
            # new doc
            new = True
            if self.doc.is_new:
                doc = self.doc
            else:
                doc = self.doclist.get_new_doc()

        doc.add_page(img, line_boxes)

        if self.doc.docid == doc.docid:
            self.show_page(self.doc.pages[-1], force_refresh=True)

        if new:
            factory = self.job_factories['label_predictor_on_new_doc']
            job = factory.make(doc)
            job.connect("predicted-labels", lambda predictor, d, predicted:
                        GLib.idle_add(self.__on_predicted_labels, doc,
                                      predicted))
            self.schedulers['main'].schedule(job)
        else:
            self.upd_index({doc}, new=False)

    def __on_predicted_labels(self, doc, predicted_labels):
        for label in self.docsearch.label_list:
            if label in predicted_labels:
                self.docsearch.add_label(doc, label, update_index=False)
        self.upd_index({doc}, new=True)
        self.refresh_label_list()

    def on_page_img_rendered(self, renderer, page_nb, nb_pages):
        if page_nb == nb_pages:
            self.set_progression(None, 0.0, None)
        else:
            self.set_progression(None, float(page_nb) / nb_pages,
                                 _("Examining imported file(s) ..."))

    def on_page_img_rendering_error(self, renderer):
        # the only known problem is when we get MemoryError for some reason
        # after some pages
        # --> for now, just hide the problem hidden under the carpet
        self.set_progression(None, 0.0, None)

    def upd_index(self, docs, new=False):
        new_docs = set()
        upd_docs = set()
        del_docs = set()

        for doc in docs:
            if not new and doc.is_new:
                # assume deleted
                del_docs.add(doc)
            elif new:
                new_docs.add(doc)
            else:
                upd_docs.add(doc)

        self.refresh_docs({doc})
        job = self.job_factories['index_updater'].make(
            self.docsearch, new_docs=new_docs, upd_docs=upd_docs,
            del_docs=del_docs, optimize=False, reload_list=False)
        self.schedulers['index'].schedule(job)

    def hide_export_dialog(self):
        # force refresh of the current page
        self._hide_export_dialog()
        if self.page is not None:
            self.show_page(self.page, force_refresh=True)

    def on_export_start(self):
        self.set_mouse_cursor("Busy")
        self.set_progression(None, 0.0, _("Exporting ..."))

    def on_export_progress(self, current, total):
        self.set_progression(None, current / total, _("Exporting ..."))

    def on_export_done(self, exporter):
        self.set_mouse_cursor("Normal")
        self.set_progression(None, 0.0, None)
        show_msg(
            parent=self.window,
            title=_("Export finished"),
            msg=_("Export of {} as {} finished").format(
                str(exporter.obj), str(exporter.export_format)
            ),
            notify_type="document-save"
        )

    def on_export_error(self, exporter, error):
        self.set_mouse_cursor("Normal")
        self.set_progression(None, 0.0, None)
        msg = _("Export failed: {}").format(str(error))
        flags = (Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog = Gtk.MessageDialog(transient_for=self.window,
                                   flags=flags,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=msg)
        dialog.connect("response", lambda dialog, response:
                       GLib.idle_add(dialog.destroy))
        dialog.show_all()
