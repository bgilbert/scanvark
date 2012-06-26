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
import yaml

class ScanvarkConfig(object):
    def __init__(self, conffile):
        with open(conffile) as fh:
            config = yaml.safe_load(fh)

        self.device = config['device']
        self.device_config = config.get('scan-settings', {})

        self.source_single = config.get('single-source', None)
        self.source_double = config.get('double-source', None)

        self.prepend_new_pages = config.get('page-order') == 'reverse'
        def get_rotation(key):
            val = config.get('rotate', 0)
            return config.get(key, val)
        self.rotate_odd = get_rotation('rotate-odd')
        self.rotate_even = get_rotation('rotate-even')

        self.jpeg_quality = config.get('jpeg-quality', 95)

        self.thumbnail_size = config.get('thumbnail-size', (200, 150))

        defaults = config.get('defaults', {})
        self.default_color = defaults.get('color', True)
        self.default_double_sided = defaults.get('double-sided', False)
        self.default_resolution = defaults.get('resolution', 150)
