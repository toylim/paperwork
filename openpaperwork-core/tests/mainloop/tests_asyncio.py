import openpaperwork_core.mainloop.tests


class TestCallback(openpaperwork_core.mainloop.tests.AbstractTestCallback):
    def get_plugin_name(self):
        return "openpaperwork_gtk.mainloop.glib"


class TestPromise(openpaperwork_core.mainloop.tests.AbstractTestPromise):
    def get_plugin_name(self):
        return "openpaperwork_gtk.mainloop.glib"
