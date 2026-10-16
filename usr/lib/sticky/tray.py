#!/usr/bin/python3

# The tray icon. On panels that show StatusNotifierItems themselves, like KDE
# Plasma, the icon is exported as a StatusNotifierItem with a DBusMenu, so the
# panel draws it and its menu natively. XApp.StatusIcon has no such backend: it
# falls back to an XEmbed icon there, which reaches the panel only through
# xembedsniproxy, and its clicks get lost under Wayland. Elsewhere XApp is used.

import os

from gi.repository import Gio, GLib, Gtk, XApp

WATCHER_NAME = 'org.kde.StatusNotifierWatcher'
WATCHER_PATH = '/StatusNotifierWatcher'
ITEM_PATH = '/StatusNotifierItem'
MENU_PATH = '/MenuBar'

ITEM_XML = '''
<node>
  <interface name='org.kde.StatusNotifierItem'>
    <property name='Category' type='s' access='read'/>
    <property name='Id' type='s' access='read'/>
    <property name='Title' type='s' access='read'/>
    <property name='Status' type='s' access='read'/>
    <property name='WindowId' type='i' access='read'/>
    <property name='IconName' type='s' access='read'/>
    <property name='IconThemePath' type='s' access='read'/>
    <property name='OverlayIconName' type='s' access='read'/>
    <property name='AttentionIconName' type='s' access='read'/>
    <property name='AttentionMovieName' type='s' access='read'/>
    <property name='ToolTip' type='(sa(iiay)ss)' access='read'/>
    <property name='ItemIsMenu' type='b' access='read'/>
    <property name='Menu' type='o' access='read'/>
    <method name='ContextMenu'>
      <arg name='x' type='i' direction='in'/>
      <arg name='y' type='i' direction='in'/>
    </method>
    <method name='Activate'>
      <arg name='x' type='i' direction='in'/>
      <arg name='y' type='i' direction='in'/>
    </method>
    <method name='SecondaryActivate'>
      <arg name='x' type='i' direction='in'/>
      <arg name='y' type='i' direction='in'/>
    </method>
    <method name='Scroll'>
      <arg name='delta' type='i' direction='in'/>
      <arg name='orientation' type='s' direction='in'/>
    </method>
    <method name='ProvideXdgActivationToken'>
      <arg name='token' type='s' direction='in'/>
    </method>
    <signal name='NewTitle'/>
    <signal name='NewIcon'/>
    <signal name='NewToolTip'/>
    <signal name='NewStatus'>
      <arg name='status' type='s'/>
    </signal>
  </interface>
</node>
'''

MENU_XML = '''
<node>
  <interface name='com.canonical.dbusmenu'>
    <property name='Version' type='u' access='read'/>
    <property name='TextDirection' type='s' access='read'/>
    <property name='Status' type='s' access='read'/>
    <property name='IconThemePath' type='as' access='read'/>
    <method name='GetLayout'>
      <arg name='parentId' type='i' direction='in'/>
      <arg name='recursionDepth' type='i' direction='in'/>
      <arg name='propertyNames' type='as' direction='in'/>
      <arg name='revision' type='u' direction='out'/>
      <arg name='layout' type='(ia{sv}av)' direction='out'/>
    </method>
    <method name='GetGroupProperties'>
      <arg name='ids' type='ai' direction='in'/>
      <arg name='propertyNames' type='as' direction='in'/>
      <arg name='properties' type='a(ia{sv})' direction='out'/>
    </method>
    <method name='GetProperty'>
      <arg name='id' type='i' direction='in'/>
      <arg name='name' type='s' direction='in'/>
      <arg name='value' type='v' direction='out'/>
    </method>
    <method name='Event'>
      <arg name='id' type='i' direction='in'/>
      <arg name='eventId' type='s' direction='in'/>
      <arg name='data' type='v' direction='in'/>
      <arg name='timestamp' type='u' direction='in'/>
    </method>
    <method name='EventGroup'>
      <arg name='events' type='a(isvu)' direction='in'/>
      <arg name='idErrors' type='ai' direction='out'/>
    </method>
    <method name='AboutToShow'>
      <arg name='id' type='i' direction='in'/>
      <arg name='needUpdate' type='b' direction='out'/>
    </method>
    <method name='AboutToShowGroup'>
      <arg name='ids' type='ai' direction='in'/>
      <arg name='updatesNeeded' type='ai' direction='out'/>
      <arg name='idErrors' type='ai' direction='out'/>
    </method>
    <signal name='ItemsPropertiesUpdated'>
      <arg name='updatedProps' type='a(ia{sv})'/>
      <arg name='removedProps' type='a(ias)'/>
    </signal>
    <signal name='LayoutUpdated'>
      <arg name='revision' type='u'/>
      <arg name='parent' type='i'/>
    </signal>
    <signal name='ItemActivationRequested'>
      <arg name='id' type='i'/>
      <arg name='timestamp' type='u'/>
    </signal>
  </interface>
</node>
'''

def create_tray_icon(connection, icon_name, title, body, on_activate, on_secondary_activate):
    """
    Returns a tray icon with set_menu(items) and destroy(). Each menu item is
    (label, callback, radio) with radio None for a plain item or the radio
    state, or None for a separator. Callbacks get no arguments; on_activate
    and on_secondary_activate get the event time.
    """
    if connection is not None and _has_owner(connection, WATCHER_NAME):
        return StatusNotifierIcon(connection, icon_name, title, body, on_activate, on_secondary_activate)

    return XAppIcon(icon_name, title, body, on_activate, on_secondary_activate)

def _has_owner(connection, name):
    try:
        result = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                                      'NameHasOwner', GLib.Variant('(s)', (name,)), GLib.VariantType('(b)'),
                                      Gio.DBusCallFlags.NONE, -1, None)
        return result.unpack()[0]
    except GLib.Error:
        return False

class StatusNotifierIcon(object):
    def __init__(self, connection, icon_name, title, body, on_activate, on_secondary_activate):
        self.connection = connection
        self.icon_name = icon_name
        self.title = title
        self.body = body
        self.on_activate = on_activate
        self.on_secondary_activate = on_secondary_activate

        self.items = []
        self.revision = 1
        self.name_acquired = False
        self.watcher_present = False

        item_info = Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0]
        menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.item_id = connection.register_object(ITEM_PATH, item_info, self.on_item_call, self.get_item_property, None)
        self.menu_id = connection.register_object(MENU_PATH, menu_info, self.on_menu_call, self.get_menu_property, None)

        self.bus_name = 'org.kde.StatusNotifierItem-%d-1' % os.getpid()
        self.own_id = Gio.bus_own_name_on_connection(connection, self.bus_name, Gio.BusNameOwnerFlags.NONE,
                                                     self.on_name_acquired, None)
        # Plasma registers its watcher again when plasmashell restarts
        self.watch_id = Gio.bus_watch_name_on_connection(connection, WATCHER_NAME, Gio.BusNameWatcherFlags.NONE,
                                                         self.on_watcher_appeared, self.on_watcher_vanished)

    def destroy(self):
        Gio.bus_unwatch_name(self.watch_id)
        Gio.bus_unown_name(self.own_id)
        self.connection.unregister_object(self.item_id)
        self.connection.unregister_object(self.menu_id)

    def set_menu(self, items):
        self.items = items
        self.revision += 1
        self.connection.emit_signal(None, MENU_PATH, 'com.canonical.dbusmenu', 'LayoutUpdated',
                                    GLib.Variant('(ui)', (self.revision, 0)))

    def on_name_acquired(self, connection, name):
        self.name_acquired = True
        self.register()

    def on_watcher_appeared(self, connection, name, owner):
        self.watcher_present = True
        self.register()

    def on_watcher_vanished(self, connection, name):
        self.watcher_present = False

    def register(self):
        if not (self.name_acquired and self.watcher_present):
            return

        self.connection.call(WATCHER_NAME, WATCHER_PATH, WATCHER_NAME, 'RegisterStatusNotifierItem',
                             GLib.Variant('(s)', (self.bus_name,)), None, Gio.DBusCallFlags.NONE, -1, None,
                             None)

    def get_item_property(self, connection, sender, path, interface, name):
        if name == 'Category':
            return GLib.Variant('s', 'ApplicationStatus')
        elif name == 'Id':
            return GLib.Variant('s', 'sticky')
        elif name == 'Title':
            return GLib.Variant('s', self.title)
        elif name == 'Status':
            return GLib.Variant('s', 'Active')
        elif name == 'WindowId':
            return GLib.Variant('i', 0)
        elif name == 'IconName':
            return GLib.Variant('s', self.icon_name)
        elif name == 'ToolTip':
            return GLib.Variant('(sa(iiay)ss)', (self.icon_name, [], self.title, self.body.replace('\n', '<br/>')))
        elif name == 'ItemIsMenu':
            return GLib.Variant('b', False)
        elif name == 'Menu':
            return GLib.Variant('o', MENU_PATH)

        # IconThemePath and the overlay and attention icons are unused
        return GLib.Variant('s', '')

    def on_item_call(self, connection, sender, path, interface, method, params, invocation, user_data=None):
        if method == 'Activate':
            self.on_activate(0)
        elif method == 'SecondaryActivate':
            self.on_secondary_activate(0)

        # ContextMenu isn't called since the panel shows the DBusMenu itself
        invocation.return_value(None)

    def get_menu_property(self, connection, sender, path, interface, name):
        if name == 'Version':
            return GLib.Variant('u', 3)
        elif name == 'TextDirection':
            return GLib.Variant('s', 'rtl' if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL else 'ltr')
        elif name == 'Status':
            return GLib.Variant('s', 'normal')
        elif name == 'IconThemePath':
            return GLib.Variant('as', [])

    # Menu item ids are the index in self.items plus one, 0 is the root
    def get_menu_item_properties(self, item_id):
        if item_id == 0:
            return {'children-display': GLib.Variant('s', 'submenu')}

        item = self.items[item_id - 1]
        if item is None:
            return {'type': GLib.Variant('s', 'separator')}

        label, callback, radio = item
        properties = {'label': GLib.Variant('s', label.replace('_', '__'))}
        if radio is not None:
            properties['toggle-type'] = GLib.Variant('s', 'radio')
            properties['toggle-state'] = GLib.Variant('i', 1 if radio else 0)

        return properties

    def get_menu_layout(self, item_id):
        children = []
        if item_id == 0:
            for child_id in range(1, len(self.items) + 1):
                children.append(self.get_menu_layout(child_id))

        return GLib.Variant('(ia{sv}av)', (item_id, self.get_menu_item_properties(item_id), children))

    def has_menu_item(self, item_id):
        return 0 <= item_id <= len(self.items)

    def on_menu_event(self, item_id, event_id):
        if event_id != 'clicked' or not 0 < item_id <= len(self.items) or self.items[item_id - 1] is None:
            return

        # Run it after the panel has closed the menu, and with this revision's callback
        callback = self.items[item_id - 1][1]
        def run():
            callback()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(run)

    def on_menu_call(self, connection, sender, path, interface, method, params, invocation, user_data=None):
        if method == 'GetLayout':
            parent_id = params.unpack()[0]
            if not self.has_menu_item(parent_id):
                invocation.return_dbus_error('com.canonical.dbusmenu.Error', 'Unknown item %d' % parent_id)
                return

            invocation.return_value(GLib.Variant.new_tuple(GLib.Variant('u', self.revision),
                                                           self.get_menu_layout(parent_id)))
        elif method == 'GetGroupProperties':
            item_ids = params.unpack()[0] or range(len(self.items) + 1)
            properties = [(i, self.get_menu_item_properties(i)) for i in item_ids if self.has_menu_item(i)]
            invocation.return_value(GLib.Variant('(a(ia{sv}))', (properties,)))
        elif method == 'GetProperty':
            item_id, name = params.unpack()
            value = self.get_menu_item_properties(item_id).get(name) if self.has_menu_item(item_id) else None
            if value is None:
                invocation.return_dbus_error('com.canonical.dbusmenu.Error', 'Unknown property %s' % name)
                return

            invocation.return_value(GLib.Variant('(v)', (value,)))
        elif method == 'Event':
            item_id, event_id = params.unpack()[:2]
            self.on_menu_event(item_id, event_id)
            invocation.return_value(None)
        elif method == 'EventGroup':
            errors = []
            for item_id, event_id, data, timestamp in params.unpack()[0]:
                if self.has_menu_item(item_id):
                    self.on_menu_event(item_id, event_id)
                else:
                    errors.append(item_id)

            invocation.return_value(GLib.Variant('(ai)', (errors,)))
        elif method == 'AboutToShow':
            invocation.return_value(GLib.Variant('(b)', (False,)))
        elif method == 'AboutToShowGroup':
            invocation.return_value(GLib.Variant('(aiai)', ([], [])))

class XAppIcon(object):
    def __init__(self, icon_name, title, body, on_activate, on_secondary_activate):
        self.on_activate = on_activate
        self.on_secondary_activate = on_secondary_activate

        self.status_icon = XApp.StatusIcon()
        self.status_icon.set_name('sticky')
        self.status_icon.set_icon_name(icon_name)
        self.status_icon.set_tooltip_text('%s\n<i>%s</i>' % (title, body.replace('\n', '</i>\n<i>')))
        self.status_icon.set_visible(True)
        self.status_icon.connect('button-press-event', self.on_button_pressed)

    def destroy(self):
        self.status_icon.set_visible(False)
        self.status_icon = None

    def on_button_pressed(self, icon, x, y, button, time, panel_position):
        if button == 1:
            self.on_activate(time)
        elif button == 2:
            self.on_secondary_activate(time)

    def set_menu(self, items):
        menu = Gtk.Menu()
        last_radio = None
        for item in items:
            if item is None:
                menu.append(Gtk.SeparatorMenuItem())
                continue

            label, callback, radio = item
            if radio is None:
                menu_item = Gtk.MenuItem(label=label)
            else:
                menu_item = Gtk.RadioMenuItem(label=label)
                if last_radio is not None:
                    menu_item.join_group(last_radio)
                menu_item.set_active(radio)
                last_radio = menu_item

            menu_item.connect('activate', lambda widget, callback=callback: callback())
            menu.append(menu_item)

        menu.show_all()
        self.status_icon.set_secondary_menu(menu)
