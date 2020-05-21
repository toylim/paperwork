import collections
import logging
import math
import random
import statistics

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps

from openpaperwork_gtk import _


GI_AVAILABLE = False
GTK_AVAILABLE = False
PANGO_AVAILABLE = False

try:
    import gi
    from gi.repository import GObject
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        GTK_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Pango', '1.0')
        gi.require_version('PangoCairo', '1.0')
        from gi.repository import Pango
        from gi.repository import PangoCairo
        PANGO_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)
SUM_COLOR = (0, 0, 0)


class Schema(object):
    def __init__(
            self,
            column_value_id_idx,
            column_line_id_idx,
            column_axis_x_values_idx,
            column_axis_x_names_idx,
            column_axis_y_values_idx,
            column_axis_y_names_idx):
        self.column_value_id_idx = column_value_id_idx
        self.column_line_id_idx = column_line_id_idx
        self.column_axis_x_values_idx = column_axis_x_values_idx
        self.column_axis_x_names_idx = column_axis_x_names_idx
        self.column_axis_y_values_idx = column_axis_y_values_idx
        self.column_axis_y_names_idx = column_axis_y_names_idx


class ColorGenerator(object):
    def __init__(self):
        self.colors = []
        self.color_idx = -1

    def reset(self):
        self.color_idx = -1

    def __next__(self):
        self.color_idx += 1
        if self.color_idx >= len(self.colors):
            self.colors.append((
                random.randint(0, 0xFF) / 0xFF,
                random.randint(0, 0xFF) / 0xFF,
                random.randint(0, 0xFF) / 0xFF,
            ))
        return self.colors[self.color_idx]


class DrawContext(object):
    """
    Custom drawing context around cairo context, so we can change
    the scale without changing the line width.
    """
    def __init__(self, ctx):
        self.ctx = ctx

    def save(self):
        self.ctx.save()

    def restore(self):
        self.ctx.restore()

    def set_source_rgb(self, r, g, b):
        self.ctx.set_source_rgb(r, g, b)

    def set_line_width(self, line_width):
        self.ctx.set_line_width(line_width)

    def move_to(self, pt_x, pt_y):
        self.ctx.move_to(pt_x, pt_y)

    def line_to(self, pt_x, pt_y):
        self.ctx.line_to(pt_x, pt_y)

    def stroke(self):
        self.ctx.stroke()

    def translate(self, x, y):
        return DrawContextTranslated(self, x, y)

    def scale(self, x, y):
        return DrawContextScaled(self, x, y)


class DrawContextTranslated(DrawContext):
    def __init__(self, ctx, translation_x, translation_y):
        super().__init__(ctx)
        self.x = translation_x
        self.y = translation_y

    def move_to(self, pt_x, pt_y):
        self.ctx.move_to(pt_x + self.x, pt_y + self.y)

    def line_to(self, pt_x, pt_y):
        self.ctx.line_to(pt_x + self.x, pt_y + self.y)


class DrawContextScaled(DrawContext):
    def __init__(self, ctx, scale_x, scale_y):
        super().__init__(ctx)
        self.x = scale_x
        self.y = scale_y

    def move_to(self, pt_x, pt_y):
        self.ctx.move_to(pt_x * self.x, pt_y * self.y)

    def line_to(self, pt_x, pt_y):
        self.ctx.line_to(pt_x * self.x, pt_y * self.y)


class Point(object):
    def __init__(self, liststore_idx, x, y, label_x, label_y, color):
        self.liststore_idx = liststore_idx
        self.x = x
        self.y = y
        self.label_x = label_x
        self.label_y = label_y
        self.color = color

    def copy(self):
        return Point(
            self.liststore_idx,
            self.x, self.y,
            self.label_x, self.label_y,
            self.color
        )

    @staticmethod
    def merge(pts):
        merged_pt = pts[0].copy()
        merged_pt.y = statistics.mean([p.y for p in pts])
        merged_pt.label_y = "\n".join([p.label_y for p in pts])
        return merged_pt

    @staticmethod
    def merge_same_x(all_pts):
        pack = []
        last_x = None
        pts = []
        for pt in all_pts:
            if last_x is None:
                pack.append(pt)
                last_x = pt.x
            elif last_x == pt.x:
                pack.append(pt)
            else:
                pts.append(Point.merge(pack))
                last_x = pt.x
                pack = [pt]
        if len(pack) > 0:
            pts.append(Point.merge(pack))
        return pts

    @staticmethod
    def from_liststore_line(liststore_idx, line, schema, color):
        return Point(
            liststore_idx,
            line[schema.column_axis_x_values_idx],
            line[schema.column_axis_y_values_idx],
            line[schema.column_axis_x_names_idx],
            line[schema.column_axis_y_names_idx],
            color
        )

    def draw_chart(self, widget_size, draw_ctx):
        # TODO
        pass


class Line(object):
    LEGEND_CIRCLE_RADIUS = 8
    LEGEND_LINE_HEIGHT = 16
    LEGEND_SPACING = 8

    def __init__(self, line_name, points, color, line_width=1.0):
        self.line_name = line_name
        self.points = points
        self.points.sort(key=lambda pt: pt.x)
        self.color = color
        self.minmax = ((math.inf, 0), (0, 0))
        self.line_width = line_width
        for pt in points:
            self.minmax = (
                (
                    min(self.minmax[0][0], pt.x),
                    max(self.minmax[0][1], pt.x),
                ),
                (
                    min(self.minmax[1][0], pt.y),
                    max(self.minmax[1][1], pt.y),
                ),
            )

    @staticmethod
    def from_liststore_lines(line_name, liststore_lines, schema, color):
        pts = [
            Point.from_liststore_line(liststore_idx, line, schema, color)
            for (liststore_idx, line) in liststore_lines
        ]
        pts = Point.merge_same_x(pts)
        return Line(line_name, pts, color)

    @staticmethod
    def make_line_sum(other_lines):
        pts = []
        for line in other_lines:
            pts += [
                (line.line_name, pt.copy())
                for pt in line.points
            ]
        pts.sort(key=lambda pt: pt[1].x)

        total_txt = _("Total")

        last_y = collections.defaultdict(lambda: 0)
        for (line_name, pt) in pts:
            last_y[line_name] = pt.y
            pt.y = sum(last_y.values())
            pt.label_y = total_txt

        pts = [pt for (line_name, pt) in pts]
        pts = Point.merge_same_x(pts)
        return Line(total_txt, pts, SUM_COLOR, 2.0)

    def draw_chart(self, widget_size, draw_ctx):
        draw_ctx.save()
        try:
            draw_ctx.set_line_width(self.line_width)
            draw_ctx.set_source_rgb(*self.color)
            for (idx, pt) in enumerate(self.points):
                if idx == 0:
                    draw_ctx.move_to(pt.x, widget_size[1] - pt.y)
                else:
                    draw_ctx.line_to(pt.x, widget_size[1] - pt.y)
            draw_ctx.stroke()
        finally:
            draw_ctx.restore()

        draw_ctx.save()
        try:
            draw_ctx.set_source_rgb(*self.color)
            for pt in self.points:
                pt.draw_chart(widget_size, draw_ctx)
        finally:
            draw_ctx.restore()

    def draw_legend(self, widget_size, cairo_ctx, x, y):
        layout = PangoCairo.create_layout(cairo_ctx)
        layout.set_text(self.line_name, -1)
        txt_size = layout.get_size()
        if 0 in txt_size:
            return (x, y)

        cairo_ctx.save()
        try:
            txt_scale = self.LEGEND_LINE_HEIGHT / txt_size[1]

            txt_width = txt_size[0] * txt_scale
            width = txt_width
            width += 2 * self.LEGEND_CIRCLE_RADIUS
            width += 2 * self.LEGEND_SPACING
            if x + width >= widget_size[0]:
                y += self.LEGEND_LINE_HEIGHT + self.LEGEND_SPACING
                x = 0

            cairo_ctx.set_source_rgb(*self.color)
            cairo_ctx.arc(
                x + self.LEGEND_CIRCLE_RADIUS,
                y + self.LEGEND_CIRCLE_RADIUS,
                self.LEGEND_CIRCLE_RADIUS,
                0, math.pi * 2
            )
            cairo_ctx.fill()
            x += (2 * self.LEGEND_CIRCLE_RADIUS) + self.LEGEND_SPACING

            cairo_ctx.set_source_rgb(0.0, 0.0, 0.0)
            cairo_ctx.translate(x, y)
            cairo_ctx.scale(txt_scale * Pango.SCALE, txt_scale * Pango.SCALE)
            PangoCairo.update_layout(cairo_ctx, layout)
            PangoCairo.show_layout(cairo_ctx, layout)
            cairo_ctx.translate(-x, -y)

            x += txt_width + self.LEGEND_SPACING
        finally:
            cairo_ctx.restore()
        return (x, y)


class Lines(object):
    def __init__(self, schema, liststore, color_generator):
        self.schema = schema
        self.liststore = liststore
        self.color_generator = color_generator

        self.lines = []
        self.minmax = ((math.inf, 0), (0, 0),)

    def reset(self):
        self.lines = []

    def reload(self):
        self.color_generator.reset()
        lines = collections.defaultdict(list)
        for (liststore_idx, line) in enumerate(self.liststore):
            line_name = line[self.schema.column_line_id_idx]
            lines[line_name].append((liststore_idx, line))
        self.lines = [
            Line.from_liststore_lines(
                k, v, self.schema, next(self.color_generator)
            )
            for (k, v) in lines.items()
        ]
        self.lines = [Line.make_line_sum(self.lines)] + self.lines
        for line in self.lines:
            self.minmax = (
                (
                    min(self.minmax[0][0], line.minmax[0][0]),
                    max(self.minmax[0][1], line.minmax[0][1]),
                ),
                (
                    min(self.minmax[1][0], line.minmax[1][0]),
                    max(self.minmax[1][1], line.minmax[1][1]),
                ),
            )

    def draw_chart(self, widget_size, draw_ctx):
        w = self.minmax[0][1] - self.minmax[0][0]
        h = self.minmax[1][1] - self.minmax[1][0]

        if w == 0 or h == 0:
            return

        draw_ctx = draw_ctx.scale(widget_size[0] / w, widget_size[1] / h)
        widget_size = (w, h)

        draw_ctx = draw_ctx.translate(
            -self.minmax[0][0], min(0, self.minmax[1][0])
        )
        widget_size = (widget_size[0] - self.minmax[0][0], widget_size[1])

        for line in self.lines:
            line.draw_chart(widget_size, draw_ctx)

    def draw_legend(self, widget_size, cairo_ctx):
        x = 0
        y = 0
        for line in self.lines:
            (x, y) = line.draw_legend(widget_size, cairo_ctx, x, y)


class ChartDrawer(object):
    MARGIN = 5

    def __init__(self, core, schema, liststore, color_generator):
        self.core = core
        self.lines = Lines(schema, liststore, color_generator)

        self.chart_widget = Gtk.DrawingArea.new()
        self.chart_widget.set_size_request(-1, 200)
        self.chart_widget.set_visible(True)
        self.chart_widget.connect("draw", self.draw_chart)

        self.legend_widget = Gtk.DrawingArea.new()
        self.legend_widget.set_visible(True)
        self.legend_widget.set_size_request(
            # TODO(Jflesch): need better sizing
            -1, 2 * (Line.LEGEND_LINE_HEIGHT + (2 * self.MARGIN))
        )
        self.legend_widget.connect("draw", self.draw_legend)

        liststore.connect("row-changed", self.reload)
        liststore.connect("row-deleted", self.reload)
        liststore.connect("row-inserted", self.reload)
        liststore.connect("rows-reordered", self.reload)

        self.has_changed = False
        self.reload_planned = False
        self._reload()

    def reload(self, *args, **kwargs):
        self.lines.reset()
        self.chart_widget.queue_draw()
        self.legend_widget.queue_draw()
        if self.reload_planned:
            self.has_changed = True
        else:
            self.has_changed = False
            self.reload_planned = True
            promise = openpaperwork_core.promise.DelayPromise(
                self.core, delay_s=0.25
            )
            promise.then(self._reload)
            promise.schedule()

    def _reload(self):
        self.reload_planned = False
        if self.has_changed:
            self.reload()
            return
        self.lines.reload()
        self.chart_widget.queue_draw()
        self.legend_widget.queue_draw()

    def draw_chart(self, widget, cairo_ctx):
        widget_size = (
            widget.get_allocated_width() - (2 * self.MARGIN),
            widget.get_allocated_height() - (2 * self.MARGIN),
        )
        draw_ctx = DrawContext(cairo_ctx)
        draw_ctx = draw_ctx.translate(self.MARGIN, self.MARGIN)
        self.lines.draw_chart(widget_size, draw_ctx)

    def draw_legend(self, widget, cairo_ctx):
        widget_size = (
            widget.get_allocated_width() - (2 * self.MARGIN),
            widget.get_allocated_height() - (2 * self.MARGIN),
        )
        cairo_ctx.translate(self.MARGIN, self.MARGIN)
        self.lines.draw_legend(widget_size, cairo_ctx)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.color_generator = ColorGenerator()

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_charts_lines',
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)

    def gtk_charts_lines_get(
            self, liststore, *args, **kwargs):
        """
        Return a Gtk.Widget showing the specified line chart.

        Can display multiple lines on single chart.
        In the model, each row is a value (x, y) for a given line.

        Arguments:
        - model: Gtk.ListStore to use as model
        - column_value_id_idx: column in the model that contains the value IDs.
        - column_line_id_idx: column that contains the name of the line
          to which this value belongs.
        - column_axis_x_values_idx: column that contains the values for the X
          axis. Must contain integers, floats or doubles.
        - column_axis_x_names_idx: column that contains the names corresponding
          to the values on the X axis. Must be strings.
        - column_axis_y_values_idx: column that contains the values for the Y
          axis. Must contain integers, floats or doubles.
        - column_axis_y_names_idx: column that contains the names corresponding
          toi the values on the Y axis. Must be strings
        """
        schema = Schema(*args, **kwargs)
        return ChartDrawer(self.core, schema, liststore, self.color_generator)


if __name__ == "__main__":
    model = Gtk.ListStore.new((
        GObject.TYPE_STRING,  # value id
        GObject.TYPE_STRING,  # line id
        GObject.TYPE_INT64,  # value X
        GObject.TYPE_INT64,  # value Y
        GObject.TYPE_STRING,  # name X
        GObject.TYPE_STRING,  # name Y
    ))
    model_content = (
        ("value A55", "line A", 5, 5, "A5", "A5"),
        ("value B55", "line B", 5, 5, "B5", "B5"),
        ("value A67", "line A", 6, 7, "A6", "A7"),
        ("value B66", "line B", 6, 6, "B6", "B6"),
        # graph must support having many values at the same position in X
        ("value A77", "line A", 7, 7, "A7", "A7"),
        ("value A73", "line A", 7, 3, "A7", "A3"),
        ("value A79", "line A", 7, 9, "A7", "A9"),
        ("value B79", "line B", 7, 9, "B7", "B9"),
        ("value A83", "line A", 7, 3, "A8", "A3"),
        ("value B88", "line B", 7, 8, "B8", "B8"),
        ("value A97", "line A", 7, 7, "A9", "A7"),
        ("value B95", "line B", 7, 5, "B9", "B5"),
        ("value A10-5", "line A", 10, -5, "A10", "A-5"),
        ("value B910", "line B", 9, 10, "B9", "B10"),
    )
    model.clear()
    for line in model_content:
        model.append(line)

    core = openpaperwork_core.Core()
    core.load("openpaperwork_gtk.widgets.charts.lines")
    core.init()

    chart_lines = core.call_success(
        "gtk_charts_lines_get", model,
        column_value_id_idx=0,
        column_line_id_idx=1,
        column_axis_x_values_idx=2,
        column_axis_y_values_idx=3,
        column_axis_x_names_idx=4,
        column_axis_y_names_idx=5
    )

    window = Gtk.Window()
    window.set_default_size(600, 600)
    window.add(chart_lines.chart_widget)
    window.show_all()

    window_legend = Gtk.Window()
    window_legend.set_default_size(100, 100)
    window_legend.add(chart_lines.legend_widget)
    window_legend.show_all()

    Gtk.main()
