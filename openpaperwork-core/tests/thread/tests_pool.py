import openpaperwork_core.thread.tests


class TestThread(openpaperwork_core.thread.tests.AbstractTestThread):
    def get_plugin_name(self):
        return "openpaperwork_core.thread.pool"
