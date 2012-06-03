#
# Scanvark -- a Gtk-based batch scanning program
#
# Copyright (c) 2012 Benjamin Gilbert
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from bisect import bisect_left
from collections import Sequence
import glib
import gobject
import gtk
import os

_BASE_RESOLUTION = 600

class _IconViewCoordinateList(Sequence):
    '''gtk.IconView provides no API to get an icon's row and column from
    its path, so we have to find it by searching.'''

    def __init__(self, iconview):
        self._iconview = iconview

    def __len__(self):
        return len(self._iconview.get_model())

    def __iter__(self):
        return (self[i] for i in xrange(len(self)))

    def __contains__(self, item):
        return self[bisect_left(self, item)] == item

    def __getitem__(self, i):
        # returns (y, x) so the Python comparison operators work
        return (self._iconview.get_item_row((i,)),
                self._iconview.get_item_column((i,)))

    def coord_to_path(self, x, y):
        index = bisect_left(self, (y, x))
        if self[index] == (y, x):
            return (index,)
        else:
            return None


class _ListIconView(gtk.IconView):
    '''IconView thinks it is managing a two-dimensional list.  Override
    selection and arrow key behavior to be consistent with a wrapped
    one-dimensional list.'''

    def __init__(self, model):
        gtk.IconView.__init__(self, model)
        self.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.connect('button-press-event', self._button_press)
        self.connect('move-cursor', self._move_cursor)
        self._selection_anchor = None

    def _button_press(self, _wid, ev):
        cursor = self.get_cursor()
        if cursor is not None:
            cursor, _renderer = cursor
            assert len(cursor) == 1
            old = cursor[0]
        else:
            old = None
        new = self.get_path_at_pos(int(ev.x), int(ev.y))
        if new is not None:
            assert len(new) == 1
            new = new[0]

        if new is not None:
            self.set_cursor((new,))
            if old is not None and (ev.state & gtk.gdk.SHIFT_MASK):
                self._change_selection(old, new)
            elif ev.state & gtk.gdk.CONTROL_MASK:
                if self.path_is_selected((new,)):
                    self.unselect_path((new,))
                else:
                    self.select_path((new,))
                self._selection_anchor = new
            else:
                self.unselect_all()
                self.select_path((new,))
                self._selection_anchor = new

        # We need to let the default handler run to prepare for a possible
        # drag, but then we need to fix up its selection breakage afterward.
        glib.idle_add(self._button_press_fixup, self.get_selected_items(),
                priority=glib.PRIORITY_HIGH)
        return False

    def _button_press_fixup(self, saved):
        good = set(saved)
        bad = set(self.get_selected_items())
        for cur in bad - good:
            self.unselect_path(cur)
        for cur in good - bad:
            self.select_path(cur)
        return False

    def _move_cursor(self, _wid, step, number):
        entries = len(self.get_model())
        cursor = self.get_cursor()
        if cursor is not None:
            cursor, _renderer = cursor
            assert len(cursor) == 1
            old = new = cursor[0]
        elif number > 0:
            old = new = self._selection_anchor = 0
        else:
            old = new = self._selection_anchor = entries - 1

        if step == gtk.MOVEMENT_VISUAL_POSITIONS:
            # Step left/right
            new += number
        elif step == gtk.MOVEMENT_DISPLAY_LINES:
            # Step up/down
            x, y = self.get_item_column((old,)), self.get_item_row((old,))
            y += number
            path = self.coord_to_path(x, y)
            if path is not None:
                assert len(path) == 1
                new = path[0]
            elif number > 0:
                new = entries - 1
            else:
                new = 0
        elif step == gtk.MOVEMENT_PAGES:
            # Page up/down
            visible = self.get_visible_range()
            if visible is not None:
                start, end = visible
                assert len(start) == len(end) == 1
                range = end[0] - start[0] + 1
                new += range * number
            elif number > 0:
                new = entries - 1
            else:
                new = 0
        elif step == gtk.MOVEMENT_BUFFER_ENDS:
            # Home/end
            if number < 0:
                new = 0
            else:
                new = entries - 1
        else:
            raise ValueError('Unknown step: %s' % step)

        new = max(min(new, entries - 1), 0)
        self.set_cursor((new,))

        modifiers = gtk.get_current_event_state()
        if modifiers & gtk.gdk.CONTROL_MASK:
            self._selection_anchor = new
        elif modifiers & gtk.gdk.SHIFT_MASK:
            self._change_selection(old, new)
        else:
            self.unselect_all()
            self.select_path((new,))
            self._selection_anchor = new

        # Prevent the default handler from running
        self.emit_stop_by_name('move-cursor')
        return True

    def _change_selection(self, old, new):
        '''old and new are indexes.'''
        disable_direction = 1 if old < self._selection_anchor else -1
        disable = set(range(old, self._selection_anchor, disable_direction))
        enable_direction = 1 if new < self._selection_anchor else -1
        # Ensure anchor is enabled
        enable = set(range(new, self._selection_anchor + enable_direction,
                enable_direction))

        both = disable & enable
        disable -= both
        enable -= both

        for cur in disable:
            self.unselect_path((cur,))
        for cur in enable:
            self.select_path((cur,))

    def coord_to_path(self, x, y):
        return _IconViewCoordinateList(self).coord_to_path(x, y)


class _PageView(_ListIconView):
    __gsignals__ = {
        'activated': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, model):
        _ListIconView.__init__(self, model)
        self.set_pixbuf_column(model.PIXBUF_COLUMN)
        self.set_reorderable(True)
        self.connect('key-press-event', self._keypress)

    def _keypress(self, _wid, ev):
        if ev.state == 0:
            if ev.keyval == gtk.gdk.keyval_from_name('Return'):
                self.emit('activated')
                return True
            if (ev.keyval == gtk.gdk.keyval_from_name('BackSpace') or
                    ev.keyval == gtk.gdk.keyval_from_name('Delete')):
                self.delete_selected()
                return True
        return False

    def delete_selected(self):
        model = self.get_model()
        for path in sorted(self.get_selected_items(), reverse=True):
            model.remove_page(path)


class _PageToolbar(gtk.Toolbar):
    def __init__(self):
        gtk.Toolbar.__init__(self)
        self._pages_selected = False

        def add_button(stock, tip):
            button = gtk.ToolButton(stock)
            button.set_tooltip_text(tip)
            self.insert(button, -1)
            return button

        self.open_button = add_button('gtk-open', 'View pages')
        self.save_button = add_button('gtk-save-as', 'Save pages as PDF')
        self.delete_button = add_button('gtk-delete', 'Delete pages')

        self._update_sensitive()

    def set_pages_selected(self, selected):
        self._pages_selected = selected
        self._update_sensitive()

    def _update_sensitive(self):
        for wid in (self.open_button, self.save_button, self.delete_button):
            wid.set_sensitive(self._pages_selected)


class _Controls(gtk.Table):
    __gsignals__ = {
        'settings-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, config):
        gtk.Table.__init__(self, columns=2)
        self.set_border_width(5)
        row = 0

        def make_label(text):
            label = gtk.Label(text)
            label.set_alignment(1, 0.5)
            label.set_padding(5, 0)
            return label

        def make_button(text):
            button = gtk.Button(text)
            align = gtk.Alignment(xalign=0)
            align.add(button)
            return button, align

        self._resolution = gtk.combo_box_new_text()
        for i in range(0, 20):
            if _BASE_RESOLUTION % (i + 1) == 0:
                resolution = _BASE_RESOLUTION / (i + 1)
                self._resolution.append_text(str(resolution) + ' dpi')
                if resolution == config.default_resolution:
                    self._resolution.set_active(i)
        self.attach(make_label('Resolution:'), 0, 1, row, row + 1)
        self.attach(self._resolution, 1, 2, row, row + 1)
        self._resolution.connect('changed', self._settings_changed)
        row += 1

        self.color = gtk.CheckButton('Color')
        self.attach(self.color, 0, 2, row, row + 1)
        self.color.set_active(config.default_color)
        self.color.connect('toggled', self._settings_changed)
        row += 1

        self.double_sided = gtk.CheckButton('Double-sided')
        self.double_sided.set_active(config.default_double_sided)
        self.attach(self.double_sided, 0, 2, row, row + 1)
        self.double_sided.connect('toggled', self._settings_changed)
        self.set_row_spacing(row, 10)
        row += 1

        self.scan_button, align = make_button('Scan')
        self.attach(align, 1, 2, row, row + 1)
        row += 1

        self.attach(gtk.HSeparator(), 0, 2, row, row + 1, ypadding=5)
        row += 1

        self.name_field = gtk.Entry()
        self.name_field.set_width_chars(25)
        self.attach(make_label('Filename:'), 0, 1, row, row + 1)
        self.attach(self.name_field, 1, 2, row, row + 1)
        self.name_field.connect('changed',
                lambda _wid: self._update_sensitive())
        self.set_row_spacing(row, 10)
        row += 1

        self.save_button, align = make_button('Save')
        self.attach(align, 1, 2, row, row + 1)
        row += 1

        self.name_field.connect('activate',
                lambda _wid: self._activate_save())

        self._scan_running = False
        self._pages_selected = False
        self._update_sensitive()

    def _settings_changed(self, _wid):
        self.emit('settings-changed')

    def get_settings(self):
        return (
            # Resolution
            int(self._resolution.get_active_text().split(' ')[0]),
            # Color
            self.color.get_active(),
            # Double-sided
            self.double_sided.get_active(),
        )

    def set_pages_selected(self, selected):
        self._pages_selected = selected
        self._update_sensitive()

    def set_scan_running(self, running):
        self._scan_running = running
        self._update_sensitive()

    def _update_sensitive(self):
        for wid in (self.scan_button, self.double_sided, self.color,
                self._resolution):
            wid.set_sensitive(not self._scan_running)
        self.save_button.set_sensitive(self._pages_selected and
                bool(self.name_field.get_text()))

    def _activate_save(self):
        if self.save_button.get_sensitive():
            self.save_button.activate()


class _SaveView(gtk.TreeView):
    def __init__(self, model):
        gtk.TreeView.__init__(self, model)

        renderer = gtk.CellRendererText()
        renderer.set_property('width-chars', 25)
        self.append_column(gtk.TreeViewColumn('Filename', renderer,
                text=model.FILENAME_COLUMN))
        self.append_column(gtk.TreeViewColumn('Progress',
                gtk.CellRendererProgress(), value=model.PROGRESS_COLUMN,
                text=model.PROGRESS_TEXT_COLUMN))


class MainWindow(gtk.Window):
    __gsignals__ = {
        'scan': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'save': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_STRING, object)),
        'settings-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'page-opened': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (object,)),
    }

    def __init__(self, config, pagelist, savelist):
        gtk.Window.__init__(self)
        self.set_title('Scanvark')
        self.set_default_size(800, 600)

        hbox = gtk.HBox(spacing=5)
        self.add(hbox)

        def make_scroller(contained):
            scroller = gtk.ScrolledWindow()
            scroller.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
            scroller.add(contained)
            return scroller

        vbox = gtk.VBox()
        hbox.pack_start(vbox)

        self._toolbar = _PageToolbar()
        vbox.pack_start(self._toolbar, expand=False)

        self._pages = _PageView(pagelist)
        vbox.pack_start(make_scroller(self._pages))

        vbox = gtk.VBox(spacing=5)
        hbox.pack_start(vbox, expand=False)

        self._controls = _Controls(config)
        vbox.pack_start(self._controls, expand=False)

        self._jobs = _SaveView(savelist)
        vbox.pack_start(make_scroller(self._jobs))

        hbox.show_all()

        self._controls.connect('settings-changed',
                lambda _wid: self.emit('settings-changed'))
        self._pages.connect('selection-changed', self._pages_selected)
        self._pages.connect('activated',
                lambda _wid: self._controls.name_field.grab_focus())
        self._pages.connect('item-activated', lambda _wid, path:
                self.emit('page-opened', pagelist.get_page(path)))
        self._controls.scan_button.connect('clicked',
                lambda _wid: self.emit('scan'))
        self._controls.save_button.connect('clicked',
                lambda _wid: self._save())
        self._toolbar.open_button.connect('clicked',
                lambda _wid: self._open())
        self._toolbar.save_button.connect('clicked',
                lambda _wid: self._controls.name_field.grab_focus())
        self._toolbar.delete_button.connect('clicked',
                lambda _wid: self._pages.delete_selected())

        self._pages.grab_focus()

    def get_settings(self):
        return self._controls.get_settings()

    def set_scan_running(self, running):
        self._controls.set_scan_running(running)

    def _open(self):
        for path in self._pages.get_selected_items():
            self._pages.item_activated(path)

    def _save(self):
        filename = self._controls.name_field.get_text()
        if os.path.exists(filename):
            dlg = ErrorDialog(self,
                    'Destination file already exists.  Overwrite?',
                    type=gtk.MESSAGE_QUESTION,
                    buttons=gtk.BUTTONS_YES_NO)
            dlg.set_default_response(gtk.RESPONSE_NO)
            result = dlg.run()
            dlg.destroy()
            if result != gtk.RESPONSE_YES:
                return
        self.emit('save', filename, sorted(self._pages.get_selected_items()))
        self._pages.grab_focus()

    def _pages_selected(self, _wid):
        selected = bool(self._pages.get_selected_items())
        self._toolbar.set_pages_selected(selected)
        self._controls.set_pages_selected(selected)


class PageWindow(gtk.Window):
    __gsignals__ = {
        'closed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, page):
        gtk.Window.__init__(self)
        self.set_title('Page View')
        # Fudge factor for scroll bar width
        self.set_default_size(*[d + 30 for d in page.size])

        self.page = page
        self._drag_base = None

        img = gtk.Image()
        img.set_from_pixbuf(page.pixbuf)

        ebox = gtk.EventBox()
        ebox.add(img)
        ebox.connect('button-press-event', self._press)
        ebox.connect('button-release-event', self._release)
        ebox.connect('motion-notify-event', self._motion)
        # pylint thinks GdkWindow.set_cursor() doesn't exist
        # pylint: disable=E1101
        ebox.connect('realize', lambda _wid:
                ebox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.CROSSHAIR)))
        # pylint: enable=E1101

        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroller.add_with_viewport(ebox)
        self._adjustments = (scroller.get_hadjustment(),
                scroller.get_vadjustment())
        self.add(scroller)
        scroller.show_all()

        self.connect('delete-event', self._delete)

        accels = gtk.AccelGroup()
        accels.connect_group(gtk.keysyms.W, gtk.gdk.CONTROL_MASK,
                gtk.ACCEL_LOCKED, self._close_key)
        accels.connect_group(gtk.keysyms.Escape, 0,
                gtk.ACCEL_LOCKED, self._close_key)
        self.add_accel_group(accels)

    def _press(self, _wid, ev):
        if ev.button == 1:
            adjustments = [a.get_value() for a in self._adjustments]
            coords = (ev.x_root, ev.y_root)
            self._drag_base = [a + c for a, c in zip(adjustments, coords)]

    def _release(self, _wid, ev):
        if ev.button == 1:
            self._drag_base = None

    def _motion(self, _wid, ev):
        if self._drag_base is not None:
            coords = (ev.x_root, ev.y_root)
            values = [min(max(base - coord, adjustment.lower),
                    adjustment.upper - adjustment.page_size)
                    for adjustment, base, coord in
                    zip(self._adjustments, self._drag_base, coords)]
            for adjustment, value in zip(self._adjustments, values):
                adjustment.set_value(value)

    def _close_key(self, _group, _wid, _keyval, _modifier):
        self.emit('closed')
        return True

    def _delete(self, _wid, _ev):
        self.emit('closed')
        return True


class ErrorDialog(gtk.MessageDialog):
    def __init__(self, parent, message, type=gtk.MESSAGE_ERROR,
            buttons=gtk.BUTTONS_OK):
        gtk.MessageDialog.__init__(self, parent, type=type, buttons=buttons,
                flags=gtk.DIALOG_MODAL)
        self.set_title('Scanvark')
        self.set_markup(message)
