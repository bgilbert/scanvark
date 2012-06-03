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
import glib
import gobject
import gtk

from .config import ScanvarkConfig
from .save import SaveThread
from .scanner import ScannerThread
from .ui import MainWindow, PageWindow, ErrorDialog

class _PageList(gtk.ListStore):
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


class _SaveList(gtk.ListStore):
    THREAD_COLUMN = 0
    FILENAME_COLUMN = 1
    PROGRESS_COLUMN = 2
    PROGRESS_TEXT_COLUMN = 3

    def __init__(self):
        gtk.ListStore.__init__(self, object, gobject.TYPE_STRING,
                gobject.TYPE_DOUBLE, gobject.TYPE_STRING)

    def add_thread(self, thread):
        self.append([thread, thread.filename, 0, 'Initializing...'])

    def _find_thread(self, thread):
        iter = self.get_iter_first()
        while iter is not None:
            if self.get_value(iter, self.THREAD_COLUMN) is thread:
                return iter
            iter = self.iter_next(iter)
        raise KeyError()

    def progress(self, thread, count, total):
        iter = self._find_thread(thread)
        self.set_value(iter, self.PROGRESS_COLUMN, 100 * count / total)
        self.set_value(iter, self.PROGRESS_TEXT_COLUMN,
                '%d/%d pages' % (count, total))

    def remove_thread(self, thread):
        self.remove(self._find_thread(thread))
        thread.join()


class Scanvark(object):
    def __init__(self, conffile):
        gobject.threads_init()
        self._config = ScanvarkConfig(conffile)
        self._scanner = ScannerThread(self._config,
                scan_status_callback=self._scan_status_callback,
                page_callback=self._page_callback)
        self._pagelist = _PageList(self._config)
        self._savelist = _SaveList()
        self._main_window = MainWindow(self._config, self._pagelist,
                self._savelist)
        self._page_windows = {}

        self._main_window.connect('delete-event', gtk.main_quit)

        self._main_window.connect('scan',
                lambda _wid: self._scanner.scan())
        self._main_window.connect('save',
                lambda _wid, f, p: self._save_document(f, p))
        self._main_window.connect('settings-changed',
                lambda _wid: self._copy_settings_to_scanner())
        self._main_window.connect('page-opened',
                lambda _wid, page: self._open_page(page))

        self._pagelist.connect('page-removed',
                lambda _model, page: self._close_page(page))

        self._copy_settings_to_scanner()

    def run(self):
        self._scanner.start()
        self._main_window.show()
        try:	
            gtk.main()
        finally:
            self._scanner.stop()
            self._scanner.join()

    def _save_document(self, filename, page_paths):
        pages = []
        for path in page_paths:
            pages.append(self._pagelist.get_page(path))
        for path in reversed(page_paths):
            self._pagelist.remove_page(path)

        thread = SaveThread(self._config, filename, pages,
                self._save_progress_callback,
                self._save_success_callback,
                self._save_error_callback)
        self._savelist.add_thread(thread)
        thread.start()

    def _save_progress_callback(self, thread, count, total):
        # Runs in save thread
        glib.idle_add(self._savelist.progress, thread, count, total)

    def _save_success_callback(self, thread):
        # Runs in save thread
        glib.idle_add(self._savelist.remove_thread, thread)

    def _save_error_callback(self, thread, message):
        # Runs in save thread
        glib.idle_add(self._handle_save_error, thread, message)

    def _handle_save_error(self, thread, message):
        dlg = ErrorDialog(self._main_window,
                "Couldn't save file: %s" % message)
        dlg.run()
        dlg.destroy()
        # Restore pages to page list
        for page in thread.pages:
            self._pagelist.append_page(page)
        self._savelist.remove_thread(thread)

    def _copy_settings_to_scanner(self):
        (self._scanner.resolution, self._scanner.color,
                self._scanner.double_sided) = \
                self._main_window.get_settings()

    def _scan_status_callback(self, is_running):
        # Runs in scanner thread
        glib.idle_add(self._main_window.set_scan_running, is_running)

    def _page_callback(self, page):
        # Runs in scanner thread
        glib.idle_add(self._pagelist.add_page, page)

    def _open_page(self, page):
        if page not in self._page_windows:
            window = PageWindow(page)
            window.connect('closed',
                    lambda wid: self._close_page(wid.page))
            self._page_windows[page] = window
        self._page_windows[page].present()

    def _close_page(self, page):
        try:
            self._page_windows.pop(page).destroy()
        except KeyError:
            pass
