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

from cStringIO import StringIO
import gtk
import numpy
from PIL import Image
from tempfile import TemporaryFile

class Page(object):
    def __init__(self, config, image, resolution):
        self._config = config
        self._fh = TemporaryFile(prefix='scanvark-')
        image.save(self._fh, 'ppm')

        self.size = image.size

        self.thumbnail = image.copy()
        self.thumbnail.thumbnail(config.thumbnail_size, Image.ANTIALIAS)
        if self.thumbnail.mode != 'RGB':
            self.thumbnail = self.thumbnail.convert('RGB')
        self.thumbnail_pixbuf = gtk.gdk.pixbuf_new_from_array(
                numpy.asarray(self.thumbnail), gtk.gdk.COLORSPACE_RGB, 8)

        self.resolution = resolution

    def open_jpeg(self):
        self._fh.seek(0)
        image = Image.open(self._fh)
        buf = StringIO()
        image.save(buf, 'jpeg', quality=self._config.jpeg_quality)
        return StringIO(buf.getvalue())

    def finish(self):
        self._fh.close()
