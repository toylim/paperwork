import kivy
import kivy.lang.builder
import kivymd.uix.menu
import kivymd.uix.boxlayout

import openpaperwork_core


class ResponsiveBoxLayout(kivymd.uix.boxlayout.MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.media_orientation = "portrait"
        self.all_children = []
        self.children_by_name = {}
        self.focus = None

    def add_widget(self, name, widget):
        if widget in self.all_children:
            return
        if self.focus is None:
            self.focus = widget
        self.children_by_name[name] = widget
        self.all_children.append(widget)
        self._refresh()

    def on_orientation_changed(self, orientation):
        self.media_orientation = orientation
        self._refresh()

    def show(self, name):
        self.focus = self.children_by_name[name]
        self._refresh()

    def _refresh(self):
        if self.media_orientation == "portrait":
            children = [self.focus]
        else:
            children = list(self.all_children)
        super().clear_widgets()
        for w in children:
            super().add_widget(w)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.root = None
        self.menu = None

    def get_interfaces(self):
        return [
            'mainwindow',
            'kivy_screen'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'kivy',
                'defaults': ['paperwork_android.kivy'],
            },
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
        ]

    def _on_menu_button_clicked(self, button):
        self.menu.caller = button
        self.menu.open()

    def kivy_load_screens(self, screen_manager):
        self.root = kivy.lang.builder.Builder.load_file(
            self.core.call_success(
                "fs_unsafe",
                self.core.call_success(
                    "resources_get_file",
                    "paperwork_android.mainwindow.window", "window.kv"
                )
            )
        )
        screen_manager.add_widget(self.root)

        class MenuItem:
            def __init__(s, callback):
                s.callback = callback

            def on_click(s, *args, **kwargs):
                self.menu.dismiss()
                s.callback()

        menu_items = []
        self.core.call_all("app_menu_get_items", menu_items)
        menu_items = [
            {
                "text": i[0],
                "viewclass": "OneLineListItem",
                "on_release": MenuItem(i[1]).on_click,
            } for i in menu_items
        ]
        self.menu = kivymd.uix.menu.MDDropdownMenu(
            items=menu_items,
            width_mult=4,
        )

        self.root.ids.toolbar.left_action_items = [
            ['menu', self._on_menu_button_clicked],
        ]

        self.core.call_all("kivy_load_mainwindow", self.root.ids.main_area)

    def on_media_changed(self, media, orientation):
        self.root.ids.main_area.on_orientation_changed(orientation)
