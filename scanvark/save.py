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
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
import threading

class SaveThread(threading.Thread):
    def __init__(self, config, filename, pages, progress_callback,
            success_callback, error_callback):
        threading.Thread.__init__(self, name='save')
        self.filename = filename
        self.pages = pages
        self._config = config
        self._progress_callback = progress_callback
        self._success_callback = success_callback
        self._error_callback = error_callback

    # We intentionally catch all exceptions
    # pylint: disable=W0703
    def run(self):
        try:
            canvas = Canvas(self.filename + '.pdf', pageCompression=1)
            canvas.setCreator('Scanvark')
            canvas.setTitle('Scanned document')
            i = 0
            count = len(self.pages)
            for i, page in enumerate(self.pages):
                self._progress_callback(self, i, count)
                w, h = [a * 72 / page.resolution for a in page.size]
                canvas.setPageSize((w, h))
                reader = ImageReader(page.open_jpeg())
                canvas.drawImage(reader, 0, 0, width=w, height=h)
                canvas.showPage()
            self._progress_callback(self, i, count)
            canvas.save()
        except Exception, e:
            self._error_callback(self, str(e))
        else:
            for page in self.pages:
                page.finish()
            self._success_callback(self)
    # pylint: enable=W0703
