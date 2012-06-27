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
from functools import wraps
import glib
import gobject
import gtk

from .config import ScanvarkConfig
from .models import PageList, SaveList
from .save import SaveThread
from .scanner import ScannerThread
from .ui import MainWindow, PageWindow, ErrorDialog

def _ui_callback(f):
    '''Decorator that arranges for the function to be invoked as a callback
    on the UI thread.'''
    @wraps(f)
    def wrapper(*args):
        glib.idle_add(f, *args)
    return wrapper

class Scanvark(object):
    def __init__(self, conffile):
        gobject.threads_init()
        self._config = ScanvarkConfig(conffile)
        self._pagelist = PageList(self._config)
        self._savelist = SaveList()
        self._main_window = MainWindow(self._config, self._pagelist,
                self._savelist)
        self._page_windows = {}
        self._scanner = ScannerThread(self._config,
                scan_status_callback=
                        _ui_callback(self._main_window.set_scan_running),
                page_callback=
                        _ui_callback(self._pagelist.add_page),
                error_callback=
                        self._handle_scan_error
        )

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
                progress_callback=_ui_callback(self._savelist.progress),
                success_callback=_ui_callback(self._savelist.remove_thread),
                error_callback=self._handle_save_error)
        self._savelist.add_thread(thread)
        thread.start()

    @_ui_callback
    def _handle_save_error(self, thread, message):
        self._show_error("Couldn't save file: %s" % message)
        # Restore pages to page list
        for page in thread.pages:
            self._pagelist.append_page(page)
        self._savelist.remove_thread(thread)

    @_ui_callback
    def _handle_scan_error(self, message, startup_failed=False):
        self._show_error(message)
        if startup_failed:
            gtk.main_quit()

    def _show_error(self, message):
        dlg = ErrorDialog(self._main_window, message)
        dlg.run()
        dlg.destroy()

    def _copy_settings_to_scanner(self):
        (self._scanner.resolution, self._scanner.color,
                self._scanner.double_sided) = \
                self._main_window.get_settings()

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
