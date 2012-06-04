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

from __future__ import division
import gobject
import gtk

class _ListStore(gtk.ListStore):
    def _find_value(self, column, value):
        iter = self.get_iter_first()
        while iter is not None:
            if self.get_value(iter, column) is value:
                return iter
            iter = self.iter_next(iter)
        raise KeyError()


class PageList(_ListStore):
    PAGE_COLUMN = 0
    PIXBUF_COLUMN = 1
    _HANDLER_ID_COLUMN = 2

    __gsignals__ = {
        'page-removed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (object,)),
    }

    def __init__(self, config):
        _ListStore.__init__(self, object, gtk.gdk.Pixbuf, gobject.TYPE_INT)
        self._config = config

    def _page_columns(self, page):
        handler_id = page.connect('changed', self._page_changed)
        return [page, page.thumbnail_pixbuf, handler_id]

    def add_page(self, page):
        if self._config.prepend_new_pages:
            func = self.prepend
        else:
            func = self.append
        func(self._page_columns(page))

    def append_page(self, page):
        self.append(self._page_columns(page))

    def get_page(self, path):
        return self.get_value(self.get_iter(path), self.PAGE_COLUMN)

    def remove_page(self, path):
        iter = self.get_iter(path)
        page = self.get_page(path)
        page.disconnect(self.get_value(iter, self._HANDLER_ID_COLUMN))
        self.emit('page-removed', page)
        self.remove(iter)

    def _page_changed(self, page):
        iter = self._find_value(self.PAGE_COLUMN, page)
        self.set_value(iter, self.PIXBUF_COLUMN, page.thumbnail_pixbuf)


class SaveList(_ListStore):
    THREAD_COLUMN = 0
    COUNT_COLUMN = 1
    TOTAL_COLUMN = 2

    def __init__(self):
        _ListStore.__init__(self, object, gobject.TYPE_INT,
                gobject.TYPE_INT)

    def add_thread(self, thread):
        self.append([thread, 0, 0])

    def progress(self, thread, count, total):
        iter = self._find_value(self.THREAD_COLUMN, thread)
        self.set_value(iter, self.COUNT_COLUMN, count)
        self.set_value(iter, self.TOTAL_COLUMN, total)

    def remove_thread(self, thread):
        self.remove(self._find_value(self.THREAD_COLUMN, thread))
        thread.join()
