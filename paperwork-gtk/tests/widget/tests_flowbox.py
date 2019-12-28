import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from paperwork_gtk.widget import flowbox


class TestPositioning(unittest.TestCase):
    def test_position_start(self):
        widgets = [
            flowbox.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.START, (40, 20)),
        ]
        flowbox.recompute_box_positions(widgets, width=100)

        self.assertEqual(widgets[0].position, (0, 0))
        self.assertEqual(widgets[1].position, (40, 0))
        self.assertEqual(widgets[2].position, (0, 20))
        self.assertEqual(widgets[3].position, (40, 20))

    def test_position_end(self):
        widgets = [
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
        ]
        flowbox.recompute_box_positions(widgets, width=100)

        self.assertEqual(widgets[0].position, (20, 0))
        self.assertEqual(widgets[1].position, (60, 0))
        self.assertEqual(widgets[2].position, (20, 20))
        self.assertEqual(widgets[3].position, (60, 20))

    def test_position_center(self):
        widgets = [
            flowbox.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
        ]
        flowbox.recompute_box_positions(widgets, width=100)

        self.assertEqual(widgets[0].position, (10, 0))
        self.assertEqual(widgets[1].position, (50, 0))
        self.assertEqual(widgets[2].position, (10, 20))
        self.assertEqual(widgets[3].position, (50, 20))

    def test_position_startend(self):
        widgets = [
            flowbox.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
        ]
        flowbox.recompute_box_positions(widgets, width=150)

        self.assertEqual(widgets[0].position, (0, 0))
        self.assertEqual(widgets[1].position, (70, 0))
        self.assertEqual(widgets[2].position, (110, 0))
        self.assertEqual(widgets[3].position, (55, 20))

    def test_position_startend_spacing(self):
        widgets = [
            flowbox.WidgetInfo(None, Gtk.Align.START, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.END, (40, 20)),
            flowbox.WidgetInfo(None, Gtk.Align.CENTER, (40, 20)),
        ]
        flowbox.recompute_box_positions(
            widgets, width=150, spacing=(3, 4)
        )

        self.assertEqual(widgets[0].position, (0, 0))
        self.assertEqual(widgets[1].position, (67, 0))
        self.assertEqual(widgets[2].position, (110, 0))
        self.assertEqual(widgets[3].position, (55, 24))
