import atexit
import code
import os
import os.path
import readline
import rlcompleter  # noqa: F401
import time
import threading

from . import PluginBase


class HistoryConsole(code.InteractiveConsole):
    def __init__(
            self, locals=None, filename="<console>",
            histfile=os.path.expanduser("~/.console-history")):
        super().__init__(locals, filename)
        self.init_history(histfile)

    def init_history(self, histfile):
        readline.parse_and_bind("tab: complete")
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(histfile)
            except FileNotFoundError:
                pass
            atexit.register(self.save_history, histfile)

    def save_history(self, histfile):
        readline.set_history_length(1000)
        readline.write_history_file(histfile)


class ProxyCore(object):
    def __init__(self, core):
        self.core = core

    def call_all(self, *args, **kwargs):
        return self.core.call_one(
            "mainloop_execute", self.core.call_all, *args, **kwargs
        )

    def call_success(self, *args, **kwargs):
        return self.core.call_one(
            "mainloop_execute", self.core.call_success, *args, **kwargs
        )

    def call_one(self, *args, **kwargs):
        return self.core.call_one(
            "mainloop_execute", self.core.call_one, *args, **kwargs
        )


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.has_quit = False

        # used for wait():
        self.progress_condition = threading.Condition()
        self.progresses = {}
        self._previous_progresses = {}

        self.nb_windows_to_realize = 0

    def get_interfaces(self):
        return [
            'gtk_window_listener'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'data_versioning',
                'defaults': ['openpaperwork_core.data_versioning'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'paths',
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
        ]

    def init(self, core):
        super().init(core)
        data_dir = self.core.call_success("paths_get_data_dir")
        base_hist_dir = self.core.call_success(
            "fs_join", data_dir, "openpaperwork"
        )
        self.core.call_success("fs_mkdir_p", base_hist_dir)
        histfile = self.core.call_success(
            "fs_join", base_hist_dir, "interactive_history"
        )

        print("Objects provided:")
        print("  core : reference to OpenPaperwork's core")
        print("  stop(): shut down the application (but not this shell)")
        print("  exit(): stops this shell (but not the application)")
        print("  wait(): wait for all background tasks to end")
        print("  Ctrl-D / EOF: stops this shell and the application")

        console = HistoryConsole({
            "core": ProxyCore(core),
            "stop": self._stop,
            "wait": self._wait,
        }, histfile=self.core.call_success("fs_unsafe", histfile))
        threading.Thread(target=self._interact, args=(console,)).start()

    def on_gtk_window_opened(self, window):
        with self.progress_condition:
            if window.get_window() is not None:
                return

            self.nb_windows_to_realize += 1
            realize_handler_id = None

            def on_realize():
                self.nb_windows_to_realize -= 1
                window.disconnect(realize_handler_id)
                self.progress_condition.notify_all()

            realize_handler_id = window.connect("realize", on_realize)

    def on_gtk_window_closed(self, window):
        pass

    def _interact(self, console):
        console.interact()
        self._stop()

    def on_quit(self):
        self.has_quit = True

    def _stop(self):
        if self.has_quit:
            return
        print("Quitting")
        self.core.call_one(
            "mainloop_execute", self.core.call_all, "mainloop_quit_graceful"
        )

    def on_progress(self, upd_type, progress, description=None):
        progress = int(progress * 100)
        with self.progress_condition:
            if progress >= 100:
                if upd_type in self.progresses:
                    self.progresses.pop(upd_type)
                    self.progress_condition.notify_all()
            elif (upd_type not in self.progresses or
                    progress != self.progresses[upd_type]):
                self.progresses[upd_type] = progress
                self.progress_condition.notify_all()

    def _wait(self):
        # WORKAROUND(Jflesch): sometimes, for some reason, we never get the
        # notification for the end of boxes loading
        MAX_TIME = 30  # seconds

        start = time.time()
        time_diff = 0

        # wait a little, in case the call to _wait() came slightly before
        # the background task creation.
        print("Waiting for all background tasks to end")
        time.sleep(3.0)
        with self.progress_condition:
            while ((len(self.progresses) > 0 or
                    self.nb_windows_to_realize > 0) and
                    time_diff <= MAX_TIME):
                while ((len(self.progresses) > 0 or
                        self.nb_windows_to_realize > 0) and
                        time_diff <= MAX_TIME):
                    print("Waiting for all background tasks to end")
                    print("Remaining background tasks:")
                    for (upd_type, progress) in self.progresses.items():
                        print("  {}: {}%".format(upd_type, int(progress)))
                    self.progress_condition.wait(1.0)
                    time_diff = time.time() - start
                if time_diff > MAX_TIME:
                    break
                # wait again a little ; sometime background tasks are
                # sequentially removed and added
                self.progress_condition.release()
                try:
                    time.sleep(3)
                finally:
                    self.progress_condition.acquire()
        if time_diff <= MAX_TIME:
            print("All background tasks have ended")
        else:
            print("TIMEOUT")
