import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa E402


DOC_BOX_XML = """
<?xml version="1.0" encoding="utf-8"?>
<interface domain="paperwork_gtk">
  <requires lib="gtk+" version="3.20"/>
  <template class="DocBox" parent="GtkListBoxRow">
    <property name="visible">True</property>
    <style>
      <class name="doclist_item"/>
    </style>
    <child>
      <object class="GtkBox" id="internal_doc_box">
        <property name="visible">True</property>
        <property name="can_focus">False</property>
        <property name="orientation">horizontal</property>
        <style>
          <class name="border-bottom-light"/>
        </style>
        <child>
          <object class="GtkOverlay">
            <property name="visible">True</property>
            <property name="can_focus">False</property>
            <child type="overlay">
              <object class="GtkCheckButton" id="doc_box_selector">
                <property name="visible">False</property>
                <property name="can_focus">False</property>
                <property name="relief">none</property>
                <property name="valign">end</property>
                <property name="margin_left">2</property>
                <property name="margin_right">2</property>
                <property name="margin_top">2</property>
                <property name="margin_bottom">2</property>
              </object>
              <packing>
                <property name="pass_through">True</property>
              </packing>
            </child>
            <child>
              <object class="GtkImage" id="doc_thumbnail">
              <property name="visible">False</property>
              <property name="icon_name">x-office-document-symbolic</property>
              <property name="icon_size">3</property>
              <style>
                <class name="doclist_thumbnail"/>
              </style>
              </object>
            </child>
          </object>
          <packing>
            <property name="pack_type">start</property>
          </packing>
        </child>

        <child>
          <object class="GtkViewport" id="layout_bin">
            <property name="visible">True</property>
            <property name="can_focus">False</property>
          </object>
          <packing>
            <property name="pack_type">start</property>
            <property name="expand">True</property>
            <property name="fill">True</property>
          </packing>
        </child>

        <child>

              <object class="GtkBox" id="doc_actions">
                <property name="visible">False</property>
                <property name="can_focus">False</property>
                <property name="orientation">vertical</property>

                <child>
                  <object class="GtkMenuButton" id="doc_actions_menu">
                    <property name="use_action_appearance">False</property>
                    <property name="visible">True</property>
                    <property name="can_focus">False</property>
                    <property name="use_underline">False</property>
                    <property name="relief">none</property>
                    <child>
                      <object class="GtkImage">
                      <property name="visible">True</property>
                      <property name="can_focus">False</property>
                      <property name="icon_name">view-more-symbolic</property>
                      <property name="icon_size">1</property>
                      </object>
                    </child>
                  </object>
                  <packing>
                    <property name="pack_type">end</property>
                    <property name="expand">True</property>
                    <property name="fill">True</property>
                  </packing>
                </child>

              </object>
          <packing>
            <property name="pack_type">start</property>
            <property name="expand">False</property>
            <property name="fill">True</property>
          </packing>
        </child>

      </object>
    </child>
  </template>
</interface>
"""


@Gtk.Template(string=DOC_BOX_XML)
class DocBox(Gtk.ListBoxRow):
    __gtype_name__ = "DocBox"

    box = Gtk.Template.Child("internal_doc_box")
    selector = Gtk.Template.Child("doc_box_selector")
    thumbnail = Gtk.Template.Child("doc_thumbnail")
    main_actions = Gtk.Template.Child("doc_actions")
    action_menu = Gtk.Template.Child("doc_actions_menu")
    layout_bin = Gtk.Template.Child("layout_bin")


DOC_MAIN_ACTION_XML = """
<?xml version="1.0" encoding="utf-8"?>
<interface domain="paperwork_gtk">
  <requires lib="gtk+" version="3.20"/>
  <template class="DocMainAction" parent="GtkButton">
    <property name="use_action_appearance">False</property>
    <property name="visible">True</property>
    <property name="can_focus">False</property>
    <property name="use_underline">False</property>
    <property name="relief">none</property>
    <property name="has_tooltip">True</property>
    <property name="tooltip_text"></property>
    <signal name="clicked" handler="on_clicked" swapped="no" />
    <child>
      <object class="GtkImage" id="doc_main_action_image">
        <property name="visible">True</property>
        <property name="can_focus">False</property>
      </object>
    </child>
  </template>
</interface>
"""


@Gtk.Template(string=DOC_MAIN_ACTION_XML)
class DocMainAction(Gtk.Button):
    __gtype_name__ = "DocMainAction"

    img = Gtk.Template.Child("doc_main_action_image")

    def __init__(self, text, icon_name, callback, *args, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)
        self.set_tooltip_text(text)
        self.img.set_from_icon_name(icon_name, Gtk.IconSize.MENU)

    @Gtk.Template.Callback("on_clicked")
    def on_clicked(self, button):
        self.callback()
