import os
import unittest

import PIL
import PIL.Image

import openpaperwork_core

from paperwork_backend.pageedit import AbstractPageEditorUI


class FakeUI(AbstractPageEditorUI):
    CAPABILITIES = AbstractPageEditorUI.CAPABILITY_SHOW_FRAME

    def __init__(self, tests):
        self.tests = tests

    def show_preview(self, img):
        self.tests.ui_calls.append(('show_preview', img))

    def show_frame_selector(self, frame):
        self.tests.ui_calls.append(('show_frame_selector', frame))

    def highlight_frame_corner(self, x, y):
        self.tests.ui_calls.append(('highlight_frame_corner', x, y))

    def hide_frame_selector(self):
        self.tests.ui_calls.append(('hide_frame_selector',))


class TestPageEdit(unittest.TestCase):
    def setUp(self):
        self.test_img = PIL.Image.open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_img.png"
            )
        )
        self.pillowed = []
        self.ui_calls = []

        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.imgedit.color")
        self.core.load("paperwork_backend.imgedit.crop")
        self.core.load("paperwork_backend.imgedit.rotate")
        self.core.load("paperwork_backend.pageedit.pageeditor")

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def pillow_to_url(s, img, dst_uri):
                    self.pillowed.append(dst_uri)
                    return dst_uri

        self.core._load_module("fake_module", FakeModule())
        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

    def test_all(self):
        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_imgs": [
                    ("file:///paper.0.jpeg", self.test_img),
                    ("file:///paper.1.jpeg", self.test_img),
                    ("file:///paper.2.jpeg", self.test_img),
                ],
            },
        ]

        fake_ui = FakeUI(self)

        page_editor = self.core.call_success(
            "page_editor_get",
            "file:///some_work_dir/some_doc_id", 1, fake_ui
        )

        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (200, 100))
        self.assertEqual(self.ui_calls[1][0], 'hide_frame_selector')

        modifiers = page_editor.get_modifiers()
        modifiers = [e['id'] for e in modifiers]
        modifiers.sort()
        self.assertEqual(modifiers, [
            "color_equalization",
            "crop",
            "rotate_clockwise",
            "rotate_counterclockwise",
        ])

        # rotate 90°
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("rotate_clockwise").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        self.assertEqual(self.ui_calls[1][0], 'hide_frame_selector')

        # ACE
        avg_color = self.ui_calls[0][1].resize(
            (1, 1), resample=PIL.Image.BILINEAR
        ).tobytes()
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("color_equalization").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        avg_color2 = self.ui_calls[0][1].resize(
            (1, 1), resample=PIL.Image.BILINEAR
        ).tobytes()
        self.assertNotEqual(avg_color, avg_color2)
        self.assertEqual(self.ui_calls[1][0], 'hide_frame_selector')

        # crop
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("crop").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        self.assertEqual(self.ui_calls[1][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[1][1], ((0, 0), (100, 200)))

        # move the cursor close to the top right corner
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_cursor_moved(95, 5).schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[0][1], ((0, 0), (100, 200)))
        self.assertEqual(self.ui_calls[1][0], 'highlight_frame_corner')
        self.assertEqual(self.ui_calls[1][1], 100)
        self.assertEqual(self.ui_calls[1][2], 0)

        # start moving the corner
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_button_pressed(90, 10).schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[0][1], ((0, 10), (90, 200)))
        self.assertEqual(self.ui_calls[1][0], 'highlight_frame_corner')
        self.assertEqual(self.ui_calls[1][1], 90)
        self.assertEqual(self.ui_calls[1][2], 10)

        # move the corner close to the opposite one
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_cursor_moved(10, 190).schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[0][1], ((0, 190), (10, 200)))
        self.assertEqual(self.ui_calls[1], ('highlight_frame_corner', 10, 190))

        # release the button
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_button_released(10, 190).schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(self.pillowed, [])
        self.assertEqual(len(self.ui_calls), 2)
        self.assertEqual(self.ui_calls[0][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[0][1], ((0, 190), (10, 200)))
        self.assertEqual(self.ui_calls[1], ('highlight_frame_corner', 10, 190))

        # rotation again (180°)
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("rotate_clockwise").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 3)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (200, 100))
        self.assertEqual(self.ui_calls[1][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[1][1], ((0, 0), (10, 10)))
        self.assertEqual(self.ui_calls[2][0], 'highlight_frame_corner')

        # .. and again (270°)
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_modifier_selected("rotate_clockwise").schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 3)
        self.assertEqual(self.ui_calls[0][0], 'show_preview')
        self.assertEqual(self.ui_calls[0][1].size, (100, 200))
        self.assertEqual(self.ui_calls[1][0], 'show_frame_selector')
        self.assertEqual(self.ui_calls[1][1], ((90, 0), (100, 10)))
        self.assertEqual(self.ui_calls[2][0], 'highlight_frame_corner')

        # and save !
        self.pillowed = []
        self.ui_calls = []
        page_editor.on_save().schedule()
        self.core.call_all("mainloop_quit_graceful")
        self.core.call_all("mainloop")
        self.assertEqual(len(self.ui_calls), 0)
        self.assertEqual(self.pillowed, ["file:///paper.1.jpeg"])
