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
import numpy
from PIL import Image
import sane
import _sane
import threading

from .page import Page

class ScanError(Exception):
    pass


class DynamicLengthSaneDev(sane.SaneDev):
    '''If dynamic scan length is enabled in the driver, libsane reports an
    image height of -1, which causes snap() to choke.  Report an appropriate
    height, then slice off the unused bottom of the image.'''

    def get_parameters(self):
        fmt, last_frame, (x, y), depth, bytes_per_line = \
                sane.SaneDev.get_parameters(self)
        if y == -1:
            y = 20 * self.resolution
        return fmt, last_frame, (x, y), depth, bytes_per_line

    def snap(self, no_cancel=False):
        img = sane.SaneDev.snap(self, no_cancel)
        # arr[y][x][channel]
        arr = numpy.asarray(img)
        # Look for rows in X that are entirely black.
        condition = arr.any(1)
        if len(condition.shape) > 1:
            # Look for rows in channel that are entirely black.
            condition = condition.any(1)
        # Select only nonblank rows.
        return Image.fromarray(arr.compress(condition, 0))


class ScannerThread(threading.Thread):
    def __init__(self, config, scan_status_callback, page_callback,
            error_callback):
        threading.Thread.__init__(self, name='scanner')
        self.daemon = True
        self._config = config
        self._scan_status_callback = scan_status_callback
        self._page_callback = page_callback
        self._error_callback = error_callback
        self._dev = None
        self._start = threading.Event()
        self._stopping = threading.Event()
        self.resolution = None
        self.color = None
        self.double_sided = None

    # We intentionally catch all exceptions
    # pylint: disable=W0703
    def run(self):
        try:
            sane.init()
            self._setup()
        except (_sane.error, Exception), e:
            self._error_callback("Couldn't set up scanner: %s" % e, True)
            return

        while not self._stopping.is_set():
            try:
                self._run_iteration()
            except (_sane.error, Exception), e:
                self._error_callback("Scan failed: %s" % e)
                # Try to reset scanner
                try:
                    self._dev.cancel()
                    self._dev.close()
                except (_sane.error, Exception), e:
                    pass
                try:
                    self._setup()
                except (_sane.error, Exception), e:
                    self._error_callback("Couldn't reinitialize scanner: %s"
                            % e)
                    return
            finally:
                self._scan_status_callback(False)
    # pylint: enable=W0703

    def _setup(self):
        self._dev = DynamicLengthSaneDev(self._config.device)
        for k, v in self._config.device_config.iteritems():
            setattr(self._dev, k, v)

    def _run_iteration(self):
        # Wait for a start event or button press
        while not self._start.wait(0.1):
            # Poll the scan button.
            if self._scan_button:
                break

        # Check if we're shutting down
        if self._stopping.is_set():
            return

        # Reset start event
        self._start.clear()

        # Configure scanner
        # pylint chokes on SaneDev's dynamic attributes
        # pylint: disable=W0201
        self._scan_status_callback(True)
        self._dev.resolution = self.resolution
        if self.color:
            self._dev.mode = 'color'
        else:
            self._dev.mode = 'gray'
        if self.double_sided:
            self._dev.source = self._config.source_double
        else:
            self._dev.source = self._config.source_single
        # pylint: enable=W0201

        # Scan
        odd = True
        for img in self._scan_pages():
            page = Page(self._config, img, self.resolution,
                    self._config.rotate_odd if odd else
                    self._config.rotate_even)
            self._page_callback(page)
            odd = not odd

    def _scan_pages(self):
        '''Reimplementation of sane._SaneIterator which doesn't choke on
        _sane exceptions.'''
        try:
            while True:
                self._dev.start()
                yield self._dev.snap(True)
        except _sane.error, e:
            if e != 'Document feeder out of documents':
                # We can't reraise the exception as-is because _sane.error
                # is a string exception, which is illegal in modern Python
                raise ScanError(e)
        finally:
            self._dev.cancel()

    def scan(self):
        # Runs in UI thread
        self._start.set()

    def stop(self):
        # Runs in UI thread
        self._stopping.set()
        self._start.set()

    @property
    def _scan_button(self):
        # The scan button is accessed via a SANE read-only setting called
        # "scan", which conflicts with the SaneDev.scan() method, so we have
        # to go the long way around.
        try:
            index = self._dev['scan'].index
            return bool(self._dev.__dict__['dev'].get_option(index))
        except KeyError:
            return False
