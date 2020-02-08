import collections
import logging
import threading

try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    # workaround so chkdeps can still be called
    class Gtk(object):
        class Box(object):
            pass

        class Widget(object):
            pass

    GTK_AVAILABLE = False


import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class WidgetInfo(object):
    def __init__(self, widget, alignment, size=None):
        self.widget = widget
        self.alignment = alignment
        if size is not None:
            self.size = (int(size[0]), int(size[1]))
        else:
            self.size = (0, 0)
        self.position = (0, 0)
        self.visible = False
        self.size_allocate_handler_id = -1

    def update_widget_size(self):
        if self.widget is None:  # test mode
            return
        self.size = (
            self.widget.get_preferred_width()[0],
            self.widget.get_preferred_height()[0],
        )

    def is_visible(self):
        if self.widget is None:  # test mode
            return True
        return self.widget.get_visible()

    def __eq__(self, o):
        if self is o:
            return True
        return self.widget == o


def recompute_height_for_width(widgets, width, spacing=(0, 0)):
    height = spacing[1]
    line_height = 0
    line_width = 0
    for widget in widgets:
        if not widget.is_visible():
            continue
        if widget.size == (0, 0):
            widget.update_widget_size()
        if line_width + widget.size[0] + spacing[0] > width + 1:
            height += spacing[1]
            height += line_height
            line_width = 0
            line_height = 0
        line_width += spacing[0]
        line_width += widget.size[0]
        line_height = max(line_height, widget.size[1])
    height += line_height
    height += spacing[1]
    return height


def recompute_box_positions(core, widgets, width, spacing=(0, 0)):
    core.call_all("on_perfcheck_start", "recompute_box_positions")

    # build lines
    lines = []
    line_heights = []
    line = []
    line_width = spacing[0]
    line_height = 0
    for widget in widgets:
        if not widget.is_visible():
            continue
        widget.update_widget_size()
        if line_width + widget.size[0] + spacing[0] > width + 1:
            lines.append(line)
            line_heights.append(line_height)
            line = []
            line_width = 0
            line_height = 0
        line.append(widget)
        line_width += spacing[0]
        line_width += widget.size[0]
        line_height = max(line_height, widget.size[1])
    lines.append(line)
    line_heights.append(line_height)

    # sort widgets by alignment in each line
    def sort_widgets_per_alignments(widgets):
        out = {
            Gtk.Align.START: [],
            Gtk.Align.CENTER: [],
            Gtk.Align.END: [],
        }
        for widget in widgets:
            out[widget.alignment].append(widget)
        return out

    lines = [sort_widgets_per_alignments(line) for line in lines]

    max_nb_columns = 0

    # position widgets in lines
    height = spacing[1]
    for (line, line_height) in zip(lines, line_heights):
        nb_columns = 0
        w_start = 0
        w_end = width

        # start
        for widget in line[Gtk.Align.START]:
            nb_columns += 1
            w_start += spacing[0]
            widget.position = (w_start, height)
            w_start += widget.size[0]

        # end
        line[Gtk.Align.END].reverse()
        for widget in line[Gtk.Align.END]:
            nb_columns += 1
            w_end -= spacing[0]
            w_end -= widget.size[0]
            widget.position = (w_end, height)

        # center
        w_center = sum(w.size[0] for w in line[Gtk.Align.CENTER])
        w_center += spacing[0] * (len(line[Gtk.Align.CENTER]) - 1)
        w_center = (width - w_center) / 2
        w_orig = w_center
        for widget in line[Gtk.Align.CENTER]:
            nb_columns += 1
            if w_center != w_orig:
                w_center += spacing[0]
            widget.position = (int(w_center), int(height))
            w_center += widget.size[0]

        height += line_height
        height += spacing[1]

        if nb_columns > max_nb_columns:
            max_nb_columns = nb_columns

    core.call_all(
        "on_perfcheck_stop", "recompute_box_positions",
        nb_boxes=len(widgets)
    )
    return (widgets, (max_nb_columns, len(lines)))


class CustomFlowLayout(Gtk.Box):
    __gsignals__ = {
        'widget_visible': (
            GObject.SignalFlags.RUN_LAST, None, (Gtk.Widget,)
        ),
        'widget_hidden': (
            GObject.SignalFlags.RUN_LAST, None, (Gtk.Widget,)
        ),
        'layout_rearranged': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, core, spacing=(0, 0), scrollbars=None):
        super().__init__()
        self.mutex = threading.RLock()
        self.core = core

        self.widgets = collections.OrderedDict()

        self.spacing = spacing
        self.vadjustment = None
        self.layout_max = (0, 0)

        self.set_has_window(False)
        self.set_redraw_on_allocate(False)

        self.connect("size-allocate", self._on_size_allocate)
        self.connect("add", self._on_add)
        self.connect("remove", self._on_remove)

        if scrollbars is not None:
            self.vadjustment = scrollbars.get_vadjustment()
            self.vadjustment.connect(
                "value-changed", self._on_vadj_value_changed
            )

    def _on_add(self, _, widget):
        self.queue_resize()

    def _on_remove(self, _, widget):
        with self.mutex:
            w = self.widgets.pop(widget)
            self.queue_draw()
            self.queue_resize()
            w.widget.disconnect(w.size_allocate_handler_id)
            w.size_allocate_handler_id = -1

    def do_forall(self, include_internals: bool, callback, callback_data=None):
        if not hasattr(self, 'mutex'):
            return
        with self.mutex:
            if not hasattr(self, 'widgets'):
                return
            widgets = self.widgets.copy()
            for widget in widgets:
                callback(widget)

    def get_widget_at(self, x, y):
        with self.mutex:
            widgets = self.widgets.copy().values()
            for widget in widgets:
                min_x = widget.position[0] - self.spacing[0]
                min_y = widget.position[1] - self.spacing[1]
                max_x = widget.position[0] + widget.size[0] + self.spacing[0]
                max_y = widget.position[1] + widget.size[1] + self.spacing[1]
                if min_x <= x and x <= max_x and min_y <= y and y <= max_y:
                    return widget.widget
            return None

    def get_widget_position(self, widget):
        with self.mutex:
            return self.widgets[widget].position

    def add_child(self, widget, alignment):
        with self.mutex:
            w = WidgetInfo(widget, alignment)
            self.widgets[widget] = w
            self.add(widget)
            w.size_allocate_handler_id = w.widget.connect(
                "size-allocate", self._on_widget_size_allocate
            )

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.WIDTH_FOR_HEIGHT

    def do_get_preferred_width(self):
        with self.mutex:
            min_width = 0
            nat_width = 0
            for widget in self.widgets.values():
                widget.update_widget_size()
                min_width = max(widget.size[0], min_width)
                nat_width += widget.size[0]
            return (min_width, nat_width)

    def do_get_preferred_height_for_width(self, width):
        with self.mutex:
            height = recompute_height_for_width(
                self.widgets.values(), width, self.spacing
            )
            return (height, height)

    def do_get_preferred_height(self):
        (min_width, nat_width) = self.do_get_preferred_width()
        return self.do_get_preferred_height_for_width(min_width)

    def do_get_preferred_width_for_height(self, height):
        return self.do_get_preferred_width()

    def _on_size_allocate(self, _, allocation):
        with self.mutex:
            (_, self.layout_max) = recompute_box_positions(
                self.core, self.widgets.values(), allocation.width,
                self.spacing
            )

            for widget in self.widgets.values():
                widget.update_widget_size()
                rect = Gdk.Rectangle()
                rect.x = allocation.x + widget.position[0]
                rect.y = allocation.y + widget.position[1]
                rect.width = widget.size[0]
                rect.height = widget.size[1]
                widget.widget.size_allocate(rect)
        self.emit('layout_rearranged')

    def get_max_nb_columns(self):
        return self.layout_max[0]

    def get_nb_lines(self):
        return self.layout_max[1]

    def update_visibility(self):
        with self.mutex:
            if self.vadjustment is None:
                return

            # assumes the vadjustment values are in pixels
            lower = self.vadjustment.get_lower()
            p_min = self.vadjustment.get_value() - lower
            p_max = (
                self.vadjustment.get_value() +
                self.vadjustment.get_page_size() -
                lower
            )

            for widget in self.widgets.values():

                p_lower = widget.position[1]
                p_upper = widget.position[1] + widget.size[1]
                visible = (p_min <= p_upper and p_lower <= p_max)
                if widget.visible != visible:
                    widget.visible = visible
                    if visible:
                        self.emit("widget_visible", widget.widget)
                    else:
                        self.emit("widget_hidden", widget.widget)

    def is_widget_visible(self, widget):
        with self.mutex:
            w = self.widgets.get(widget, None)
            if w is None:
                return False
            return w.visible

    def _on_vadj_value_changed(self, vadjustment):
        self.update_visibility()

    def _on_widget_size_allocate(self, widget, allocation):
        self.update_visibility()

    def _on_destroy(self, _):
        with self.mutex:
            if not hasattr(self, 'widgets'):
                return
            for widget in self.widgets.keys():
                widget.unparent()
            self.widgets = collections.OrderedDict()

    def get_width_without_margins(self, nb_widgets=1):
        nb_widgets = min(len(self.widgets), nb_widgets)
        layout_width = self.get_allocated_width()
        layout_width -= (nb_widgets + 1) * self.spacing[0]
        if layout_width <= 0:
            return None
        return layout_width

        widgets = list(self.widgets.values())[:nb_widgets]
        widget_width = 0
        for w in widgets:
            widget_width += w.size[0]

        if widget_width <= 0:
            return None

        return layout_width / widget_width


if GTK_AVAILABLE:
    GObject.type_register(CustomFlowLayout)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_widget_flowlayout',
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def gtk_widget_flowlayout_new(self, spacing=(0, 0), scrollbars=None):
        assert(GLIB_AVAILABLE)
        assert(GTK_AVAILABLE)
        return CustomFlowLayout(self.core, spacing, scrollbars)