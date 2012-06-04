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
from cStringIO import StringIO
import gobject
import gtk
import numpy
from PIL import Image
from tempfile import TemporaryFile

class Page(gobject.GObject):
    __gsignals__ = {
        'changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, config, image, resolution):
        gobject.GObject.__init__(self)
        self._config = config
        self._fh = TemporaryFile(prefix='scanvark-')
        image.save(self._fh, 'ppm')

        self.resolution = resolution
        self._size = image.size
        self._rotation = 0

        self._thumbnail = image.copy()
        self._thumbnail.thumbnail(config.thumbnail_size, Image.ANTIALIAS)

    def _get_image(self):
        self._fh.seek(0)
        return self._rotate_image(Image.open(self._fh))

    @staticmethod
    def _make_pixbuf(image):
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return gtk.gdk.pixbuf_new_from_array(numpy.asarray(image),
                gtk.gdk.COLORSPACE_RGB, 8)

    def _rotate_image(self, image):
        if self._rotation == 0:
            return image
        elif self._rotation == 90:
            return image.transpose(Image.ROTATE_90)
        elif self._rotation == 180:
            return image.transpose(Image.ROTATE_180)
        elif self._rotation == 270:
            return image.transpose(Image.ROTATE_270)
        else:
            raise ValueError('Illegal rotation')

    def rotate(self, degrees):
        if degrees % 90:
            raise ValueError('90 degree rotations only')
        self._rotation += degrees
        # Canonicalize
        self._rotation -= 360 * (self._rotation // 360)
        self.emit('changed')

    @property
    def size(self):
        if self._rotation % 180:
            return reversed(self._size)
        else:
            return self._size

    @property
    def pixbuf(self):
        return self._make_pixbuf(self._get_image())

    @property
    def thumbnail_pixbuf(self):
        return self._make_pixbuf(self._rotate_image(self._thumbnail))

    def open_jpeg(self):
        image = self._get_image()
        buf = StringIO()
        image.save(buf, 'jpeg', quality=self._config.jpeg_quality)
        return StringIO(buf.getvalue())

    def finish(self):
        self._fh.close()

gobject.type_register(Page)
