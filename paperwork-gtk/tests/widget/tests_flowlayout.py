import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from paperwork_gtk.widget import flowlayout


class DummyCore(object):
    @staticmethod
    def call_all(*args, **kwargs):
        pass


class TestPositioning(unittest.TestCase):
    def test_position_start(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.START, (40, 20)),
        ]
        flowlayout.recompute_box_positions(DummyCore(), widgets, width=100)

        self.assertEqual(widgets[0].position, (0, 0))
        self.assertEqual(widgets[1].position, (40, 0))
        self.assertEqual(widgets[2].position, (0, 20))
        self.assertEqual(widgets[3].position, (40, 20))

    def test_position_end(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
        ]
        flowlayout.recompute_box_positions(DummyCore(), widgets, width=100)

        self.assertEqual(widgets[0].position, (20, 0))
        self.assertEqual(widgets[1].position, (60, 0))
        self.assertEqual(widgets[2].position, (20, 20))
        self.assertEqual(widgets[3].position, (60, 20))

    def test_position_center(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
        ]
        flowlayout.recompute_box_positions(DummyCore(), widgets, width=100)

        self.assertEqual(widgets[0].position, (10, 0))
        self.assertEqual(widgets[1].position, (50, 0))
        self.assertEqual(widgets[2].position, (10, 20))
        self.assertEqual(widgets[3].position, (50, 20))

    def test_position_startend(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
        ]
        flowlayout.recompute_box_positions(DummyCore(), widgets, width=150)

        self.assertEqual(widgets[0].position, (0, 0))
        self.assertEqual(widgets[1].position, (70, 0))
        self.assertEqual(widgets[2].position, (110, 0))
        self.assertEqual(widgets[3].position, (55, 20))

    def test_position_startend_spacing(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
        ]
        flowlayout.recompute_box_positions(
            DummyCore(), widgets, width=150, spacing=(3, 4)
        )

        self.assertEqual(widgets[0].position, (3, 4))
        self.assertEqual(widgets[2].position, (107, 4))
        self.assertEqual(widgets[1].position, (64, 4))
        self.assertEqual(widgets[3].position, (55, 28))

    def test_position_center_spacing(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (140, 200)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (140, 200)),
        ]
        flowlayout.recompute_box_positions(
            DummyCore(), widgets, width=500, spacing=(50, 50)
        )

        self.assertEqual(widgets[0].position, (85, 50))
        self.assertEqual(widgets[1].position, (275, 50))

    def test_position_center_spacing_tight(self):
        widgets = [
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (100, 100)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (100, 100)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (100, 100)),
            flowlayout.WidgetInfo(None, Gtk.Align.CENTER, (100, 100)),
        ]
        flowlayout.recompute_box_positions(
            DummyCore(), widgets, width=350, spacing=(50, 50)
        )

        self.assertEqual(widgets[0].position, (50, 50))
        self.assertEqual(widgets[1].position, (200, 50))
        self.assertEqual(widgets[2].position, (50, 200))
        self.assertEqual(widgets[3].position, (200, 200))
