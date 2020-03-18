import openpaperwork_core.spatial.tests


class TestSpatial(openpaperwork_core.spatial.tests.AbstractTest):
    def get_plugin_name(self):
        return "openpaperwork_core.spatial.rtree"
