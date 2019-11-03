"""
Plugin providing a controller object for page editing. This controller object
uses a paperwork_backend.imgedit.AbstractPageEditorUI object to tells the UI
what to do. The UI must reciprocate by transmitting some events to the
controller object.
"""

import gettext
import logging
import math

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


def compute_squared_distance(pt_a, pt_b):
    """
    Compute the distance between point A and point B, but return the square
    of the distance (because it's faster, and we usually only want to compare
    those distances between themselves).
    """
    x = pt_a[0] - pt_b[0]
    y = pt_a[1] - pt_b[1]
    return ((x * x) + (y * y))


class Corner(object):
    """
    Each instance of this class represents one of the corner of the frame.
    Modifying the coordinates of the corner modifies the frame and the
    coordinates of 2 other corners.
    """
    def __init__(self, frame, corner_x_idx, corner_y_idx):
        self.frame = frame
        self.corner_x_idx = corner_x_idx
        self.corner_y_idx = corner_y_idx

    def _get_coords(self):
        return (
            self.frame[self.corner_x_idx],
            self.frame[self.corner_y_idx]
        )

    def _set_coords(self, pt):
        (x, y) = pt
        self.frame[self.corner_x_idx] = x
        self.frame[self.corner_y_idx] = y

    coords = property(_get_coords, _set_coords)

    def compute_squared_distance(self, pt):
        return compute_squared_distance(self.coords, pt)


class Frame(object):
    def __init__(self, original):
        # convert the frame coordinates into a more convenient format
        self.frame = [
            original[0][0], original[0][1],
            original[1][0], original[1][1]
        ]
        self.corners = [
            Corner(self.frame, corner_idx_x, corner_idx_y)
            for (corner_idx_x, corner_idx_y)
            in ((0, 1), (2, 3), (0, 3), (2, 1))
        ]

    def get_corner(self, x, y):
        """
        Arguments:
        x - cursor position in X
        y - cursor position in Y
        """
        # We always return one of the corners: the closest one
        pt = (x, y)
        m_corner = (math.inf, None)
        for corner in self.corners:
            dist = corner.compute_squared_distance(pt)
            if dist < m_corner[0]:
                m_corner = (dist, corner)
        assert(m_corner[1] is not None)
        return m_corner[1]

    @property
    def coords(self):
        return (
            (
                min(self.frame[0], self.frame[2]),
                min(self.frame[1], self.frame[3]),
            ),
            (
                max(self.frame[0], self.frame[2]),
                max(self.frame[1], self.frame[3]),
            ),
        )


class PageEditor(object):
    def __init__(self, core, doc_url, page_idx, page_editor_ui):
        self.core = core
        self.ui = page_editor_ui
        self.doc_url = doc_url
        self.page_idx = page_idx

        if doc_url is not None:
            page_url = self.core.call_success(
                "page_get_img_url", doc_url, page_idx, write=False
            )
            self.original_img = self.core.call_success(
                "url_to_pillow", page_url
            )

            # The frame coordinates we keep here are relative to the original
            # image (not the resulting image, that can, for instance, be
            # rotated)
            # TODO(Jflesch): We should use libpillowfight.scan_border()
            # to predefined an useful frame.
            self.original_frame = ((0, 0), self.original_img.size)
        else:
            self.original_img = None
            self.original_frame = ((0, 0), (0, 0))

        self.frame = Frame(self.original_frame)
        modifiers = []
        self.core.call_all("img_editor_get_names", modifiers)

        self.modifier_descriptors = {}
        if 'color_equalization' in modifiers:
            self.modifier_descriptors['color_equalization'] = {
                "id": "color_equalization",
                "name": _("Color equalization"),
                "modifier": 'color_equalization',
                "default_kwargs": {},
                "need_frame": False,
                "togglable": False,
            }
        if ('cropping' in modifiers
                    and self.ui.can(self.ui.CAPABILITY_SHOW_FRAME)):
            self.modifier_descriptors['crop'] = {
                "id": "crop",
                "name": _("Cropping"),
                "modifier": 'cropping',
                "default_kwargs": {'frame': self.original_frame},
                "need_frame": True,
                "togglable": True,
                "enabled": False,
            }
        if 'rotation' in modifiers:
            self.modifier_descriptors['rotate_clockwise'] = {
                "id": "rotate_clockwise",
                "name": _("Clockwise Rotation"),
                "modifier": 'rotation',
                "default_kwargs": {'angle': 90},
                "need_frame": False,
                "togglable": False,
            }
            self.modifier_descriptors['rotate_counterclockwise'] = {
                "id": "rotate_counterclockwise",
                "name": _("Counterclockwise Rotation"),
                "modifier": 'rotation',
                "default_kwargs": {'angle': -90},
                "need_frame": False,
                "togglable": False,
            }
        self.active_modifiers = []
        # image sizes before transformation of each modifier
        self.img_sizes = []
        self.highlighted_corner = None
        self.selected_corner = None

        if self.ui is not None:
            self._refresh_preview()
            self._refresh_frame()

    def get_modifiers(self):
        return self.modifier_descriptors.values()

    def _recompute_frame(self):
        frame = self.frame.coords
        for (e, img_size) in zip(self.active_modifiers, self.img_sizes):
            if hasattr(e, 'frame'):
                e.frame = frame
            frame = e.transform_frame(img_size, frame)
        return frame

    def _needs_frame(self):
        if not self.ui.can(self.ui.CAPABILITY_SHOW_FRAME):
            return
        for e in self.active_modifiers:
            if hasattr(e, 'frame'):
                return True
        return False

    def _refresh_modifiers(self):
        for modifier in self.modifier_descriptors.values():
            enabled = False
            if modifier['togglable'] and modifier['enabled']:
                enabled = True
            self.ui.set_modifier_state(modifier['id'], enabled)

    def _refresh_preview(self):
        img = self.original_img
        self.img_sizes = []
        for e in self.active_modifiers:
            self.img_sizes.append(img.size)
            img = e.transform(img, preview=True)
        self.core.call_one("mainloop_execute", self.ui.show_preview, img)

    def _refresh_frame(self):
        if not self._needs_frame():
            self.core.call_one("mainloop_execute", self.ui.hide_frame_selector)
            return
        frame = self._recompute_frame()
        self.core.call_one(
            "mainloop_execute", self.ui.show_frame_selector, frame
        )

        if self.highlighted_corner is None:
            return

        pt = self.highlighted_corner.coords
        for (e, img_size) in zip(self.active_modifiers, self.img_sizes):
            pt = e.transform_point(img_size, pt)
        self.core.call_one(
            "mainloop_execute",
            self.ui.highlight_frame_corner,
            pt[0], pt[1]
        )

    def _on_modifier_selected(self, modifier_id):
        modifier_descriptor = self.modifier_descriptors[modifier_id]

        if modifier_descriptor['togglable'] and modifier_descriptor['enabled']:
            self.core.call_all(
                "img_editor_unset",
                self.active_modifiers,
                modifier_descriptor['modifier']
            )
            modifier_descriptor['enabled'] = True
        else:
            self.core.call_all(
                "img_editor_set",
                self.active_modifiers,
                modifier_descriptor['modifier'],
                **modifier_descriptor['default_kwargs']
            )
            modifier_descriptor['enabled'] = False

        self._refresh_modifiers()
        self._refresh_preview()
        self._refresh_frame()

    def on_modifier_selected(self, modifier_id):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._on_modifier_selected, args=(modifier_id,)
        )

    def _untransform_pt(self, x, y):
        pt = (x, y)
        for (e, img_size) in zip(
                    reversed(self.active_modifiers),
                    reversed(self.img_sizes)
                ):
            pt = e.untransform_point(img_size, pt)
        return pt

    def _on_cursor_moved(self, x, y):
        (x, y) = self._untransform_pt(x, y)
        if self.selected_corner is not None:
            self.selected_corner.coords = (x, y)
        self.highlighted_corner = self.frame.get_corner(x, y)
        self._refresh_frame()

    def on_cursor_moved(self, x, y):
        return openpaperwork_core.promise.Promise(
            self.core, self._on_cursor_moved, args=(x, y)
        )

    def _on_button_pressed(self, x, y):
        (orig_x, orig_y) = self._untransform_pt(x, y)
        self.selected_corner = self.frame.get_corner(orig_x, orig_y)
        self._on_cursor_moved(x, y)

    def on_button_pressed(self, x, y):
        return openpaperwork_core.promise.Promise(
            self.core, self._on_button_pressed, args=(x, y)
        )

    def _on_button_released(self, x, y):
        self.selected_corner = None
        self._on_cursor_moved(x, y)

    def on_button_released(self, x, y):
        return openpaperwork_core.promise.Promise(
            self.core, self._on_button_pressed, args=(x, y)
        )

    def _on_save(self):
        img = self.original_img
        for e in self.active_modifiers:
            img = e.transform(img, preview=False)
        page_url = self.core.call_success(
            "page_get_img_url", self.doc_url, self.page_idx, write=True
        )
        self.core.call_success("pillow_to_url", img, page_url)
        self.ui.on_edit_end(self.doc_url, self.page_idx)

    def on_save(self):
        return openpaperwork_core.promise.ThreadedPromise(
            self.core, self._on_save
        )

    def on_cancel(self):
        self.active_modifiers = []
        self.ui.on_edit_end(self.doc_url, self.page_idx)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return ['page_editor']

    def get_deps(self):
        return {
            'interfaces': [
                ('img_editor', [
                    'paperwork_backend.imgedit.color',
                    'paperwork_backend.imgedit.crop',
                    'paperwork_backend.imgedit.rotate',
                ]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio']),
                ('pillow', [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]),
            ],
        }

    def page_editor_get(self, doc_url, page_idx, page_editor_ui):
        return PageEditor(self.core, doc_url, page_idx, page_editor_ui)
