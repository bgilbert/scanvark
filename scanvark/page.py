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

        self.resolution = resolution
        self.size = image.size

        thumbnail = image.copy()
        thumbnail.thumbnail(config.thumbnail_size, Image.ANTIALIAS)
        self.thumbnail_pixbuf = self._make_pixbuf(thumbnail)

    def _get_image(self):
        self._fh.seek(0)
        return Image.open(self._fh)

    def _make_pixbuf(self, image):
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return gtk.gdk.pixbuf_new_from_array(numpy.asarray(image),
                gtk.gdk.COLORSPACE_RGB, 8)

    def open_jpeg(self):
        image = self._get_image()
        buf = StringIO()
        image.save(buf, 'jpeg', quality=self._config.jpeg_quality)
        return StringIO(buf.getvalue())

    def finish(self):
        self._fh.close()
