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


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.has_quit = False

        # used for wait():
        self.progress_condition = threading.Condition()
        self.progresses = {}
        self._previous_progresses = {}

    def init(self, core):
        super().init(core)
        local_dir = os.path.expanduser("~/.local")
        data_dir = os.getenv(
            "XDG_DATA_HOME", os.path.join(local_dir, "share")
        )
        base_hist_dir = os.path.join(
            data_dir, "openpaperwork"
        )
        os.makedirs(base_hist_dir, exist_ok=True)
        histfile = os.path.join(base_hist_dir, "interactive_history")

        print("Objects provided:")
        print("  core : reference to OpenPaperwork's core")
        print("  stop(): shut down the application (but not this shell)")
        print("  exit(): stops this shell (but not the application)")
        print("  wait(): wait for all background tasks to end")
        print("  Ctrl-D / EOF: stops this shell and the application")

        console = HistoryConsole({
            "core": core,
            "stop": self._stop,
            "wait": self._wait,
        }, histfile=histfile)
        threading.Thread(target=self._interact, args=(console,)).start()

    def _interact(self, console):
        console.interact()
        self._stop()

    def on_quit(self):
        self.has_quit = True

    def _stop(self):
        if self.has_quit:
            return
        self.core.call_all("on_quit")
        self.core.call_all("mainloop_quit_graceful")

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
        # wait a little, in case the call to _wait() came slightly before
        # the background task creation.
        time.sleep(3.0)
        with self.progress_condition:
            while len(self.progresses) > 0:
                while len(self.progresses) > 0:
                    print("Waiting for all background tasks to end")
                    print("Remaining background tasks:")
                    for (upd_type, progress) in self.progresses.items():
                        print("  {}: {}%".format(upd_type, int(progress)))
                    self.progress_condition.wait(1.0)
                # wait again a little ; sometime background tasks are
                # sequentially removed and added
                self.progress_condition.wait(3.0)
        print("All background tasks have ended")
