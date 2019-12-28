import logging

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    CAIRO_AVAILABLE = False

try:
    from gi.repository import GObject
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class WidgetInfo(object):
    def __init__(self, widget, alignment, size=None):
        self.widget = widget
        self.alignment = alignment
        if size is not None:
            self.size = size
        else:
            self.size = (0, 0)
        self.position = (0, 0)

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
    height = 0
    line_height = 0
    line_width = 0
    for widget in widgets:
        if not widget.is_visible():
            continue
        if widget.size == (0, 0):
            widget.update_widget_size()
        if line_width + widget.size[0] >= width:
            line_width = 0
            if height > 0:
                height += spacing[1]
            height += line_height
            line_height = 0
        if line_width > 0:
            line_width += spacing[0]
        line_width += widget.size[0]
        line_height = max(line_height, widget.size[1])
    height += line_height
    return height


def recompute_box_positions(widgets, width, spacing=(0, 0)):
    # build lines
    lines = []
    line_heights = []
    line = []
    line_width = 0
    line_height = 0
    for widget in widgets:
        if not widget.is_visible():
            continue
        widget.update_widget_size()
        if line_width + widget.size[0] >= width:
            lines.append(line)
            if line_height > 0:
                line_height += spacing[1]
            line_heights.append(line_height)
            line = []
            line_width = 0
            line_height = 0
        line.append(widget)
        if line_width > 0:
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

    # position widgets in lines
    height = 0
    for (line, line_height) in zip(lines, line_heights):
        w_start = 0
        w_end = width

        # start
        for widget in line[Gtk.Align.START]:
            widget.position = (w_start, height)
            if w_start > 0:
                w_start += spacing[0]
            w_start += widget.size[0]

        # end
        line[Gtk.Align.END].reverse()
        for widget in line[Gtk.Align.END]:
            if w_end < width:
                w_end -= spacing[0]
            w_end -= widget.size[0]
            widget.position = (w_end, height)

        # center
        w_center = sum(w.size[0] for w in line[Gtk.Align.CENTER])
        w_center += spacing[0] * (len(line[Gtk.Align.CENTER]) - 1)
        w_center = (width - w_center) / 2
        w_orig = w_center
        for widget in line[Gtk.Align.CENTER]:
            widget.position = (w_center, height)
            if w_center != w_orig:
                w_center += spacing[1]
            w_center += widget.size[0]

        height += line_height

    return widgets


class CustomFlowBox(Gtk.Box):
    def __init__(self, spacing=(0, 0)):
        super().__init__()
        self.spacing = spacing
        self.widgets = []
        self.set_has_window(False)
        self.set_redraw_on_allocate(False)
        self.width = 100
        self.connect("size-allocate", self.on_size_allocate)
        self.connect("add", self.on_add)
        self.connect("remove", self.on_remove)

    def on_add(self, _, widget):
        self.widgets.append(WidgetInfo(widget, Gtk.Align.START))
        self.queue_resize()

    def on_remove(self, _, widget):
        self.widgets.remove(widget)
        self.queue_draw()
        self.queue_resize()

    def do_forall(self, include_internals: bool, callback, callback_data=None):
        for widget in self.widgets:
            callback(widget.widget)

    def _update_widgets(self):
        def chk_widget(widget):
            if widget not in self.widgets:
                self.widgets.append(WidgetInfo(widget, Gtk.Align.START))
        self.forall(chk_widget)

    def set_alignment(self, widget, alignment):
        widget_idx = self.widgets.index(widget)
        widget = self.widgets[widget_idx]
        widget.alignment = alignment
        self.queue_draw()

    def do_get_preferred_width(self):
        min_width = 0
        nat_width = 0
        for widget in self.widgets:
            widget.update_widget_size()
            min_width = max(widget.size[0], min_width)
            nat_width += widget.size[0]
        return (min_width, nat_width)

    def do_get_preferred_height_for_width(self, width):
        height = recompute_height_for_width(self.widgets, width, self.spacing)
        return (height, height)

    def do_get_preferred_height(self):
        (min_width, nat_width) = self.do_get_preferred_width()
        return self.do_get_preferred_height_for_width(min_width)

    def do_get_preferred_width_for_height(self):
        return self.do_get_preferred_width()

    def on_size_allocate(self, _, allocation):
        recompute_box_positions(self.widgets, allocation.width, self.spacing)

        for widget in self.widgets:
            widget.update_widget_size()
            rect = Gdk.Rectangle()
            rect.x = allocation.x + widget.position[0]
            rect.y = allocation.y + widget.position[1]
            rect.width = widget.size[0]
            rect.height = widget.size[1]
            widget.widget.size_allocate(rect)

    def do_destroy(self):
        for widget in self.widgets:
            widget.widget.unparent()


GObject.type_register(CustomFlowBox)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_widget_flowbox',
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo']['debian'] = 'python3-gi-cairo'
            out['cairo']['fedora'] = 'python3-gobject'
            out['cairo']['linuxmint'] = 'python3-gi-cairo'
            out['cairo']['ubuntu'] = 'python3-gi-cairo'
        if not GI_AVAILABLE:
            out['gi']['debian'] = 'python3-gi'
            out['gi']['fedora'] = 'python3-gobject-base'
            out['gi']['linuxmint'] = 'python3-gi'
            out['gi']['ubuntu'] = 'python3-gi'
        if not GTK_AVAILABLE:
            out['gtk']['debian'] = 'gir1.2-gtk-3.0'
            out['gtk']['fedora'] = 'gtk3'
            out['gtk']['gentoo'] = 'x11-libs/gtk+'
            out['gtk']['linuxmint'] = 'gir1.2-gtk-3.0'
            out['gtk']['ubuntu'] = 'gir1.2-gtk-3.0'
            out['gtk']['suse'] = 'python-gtk'

    def gtk_widget_flowbox_new(self, spacing=(0, 0)):
        assert(CAIRO_AVAILABLE)
        assert(GI_AVAILABLE)
        assert(GTK_AVAILABLE)
        return CustomFlowBox(spacing)
