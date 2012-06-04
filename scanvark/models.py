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

class PageList(gtk.ListStore):
    PAGE_COLUMN = 0
    PIXBUF_COLUMN = 1

    __gsignals__ = {
        'page-removed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (object,)),
    }

    def __init__(self, config):
        gtk.ListStore.__init__(self, object, gtk.gdk.Pixbuf)
        self._config = config

    def add_page(self, page):
        if self._config.prepend_new_pages:
            func = self.prepend
        else:
            func = self.append
        func([page, page.thumbnail_pixbuf])

    def append_page(self, page):
        self.append([page, page.thumbnail_pixbuf])

    def get_page(self, path):
        return self.get_value(self.get_iter(path), self.PAGE_COLUMN)

    def remove_page(self, path):
        self.emit('page-removed', self.get_page(path))
        self.remove(self.get_iter(path))


class SaveList(gtk.ListStore):
    THREAD_COLUMN = 0
    COUNT_COLUMN = 1
    TOTAL_COLUMN = 2

    def __init__(self):
        gtk.ListStore.__init__(self, object, gobject.TYPE_INT,
                gobject.TYPE_INT)

    def add_thread(self, thread):
        self.append([thread, 0, 0])

    def _find_thread(self, thread):
        iter = self.get_iter_first()
        while iter is not None:
            if self.get_value(iter, self.THREAD_COLUMN) is thread:
                return iter
            iter = self.iter_next(iter)
        raise KeyError()

    def progress(self, thread, count, total):
        iter = self._find_thread(thread)
        self.set_value(iter, self.COUNT_COLUMN, count)
        self.set_value(iter, self.TOTAL_COLUMN, total)

    def remove_thread(self, thread):
        self.remove(self._find_thread(thread))
        thread.join()
