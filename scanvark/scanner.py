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
import time

from .page import Page

class ScanError(Exception):
    # Class named according to method naming conventions.
    # pylint: disable=C0103
    class sanitize(object):
        '''Convert _sane's string exceptions into proper ones.
        String exceptions can't be reraised because they're illegal in modern
        Python.'''

        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type == _sane.error:
                raise ScanError(exc_val)
    # pylint: enable=C0103


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
        # Initialize SANE
        try:
            with ScanError.sanitize():
                sane.init()
        except Exception, e:
            self._error_callback("Couldn't initialize SANE: %s" % e)
            return

        # Try to initialize the scanner so that the hardware scan button
        # will work.
        try:
            self._setup()
        except Exception:
            pass

        while not self._stopping.is_set():
            try:
                self._wait_for_start()
                if self._stopping.is_set():
                    break
                self._scan_status_callback(True)
                # Wait for the scan status callback to run in the UI thread
                # before _setup() takes the GIL for perhaps 1 second
                time.sleep(0.1)
                self._setup()
                self._run_scan()
            except Exception, e:
                self._error_callback("Scan failed: %s" % e)
                self._close()
            finally:
                self._scan_status_callback(False)

        self._close()
    # pylint: enable=W0703

    def _setup(self):
        if self._dev is None:
            try:
                with ScanError.sanitize():
                    dev = DynamicLengthSaneDev(self._config.device)
                    for k, v in self._config.device_config.iteritems():
                        setattr(dev, k, v)
            except RuntimeError, e:
                # Attempted to open an invalid device
                raise ScanError(str(e))
            self._dev = dev

    def _close(self):
        if self._dev is not None:
            try:
                with ScanError.sanitize():
                    self._dev.cancel()
                    self._dev.close()
                self._dev = None
            except ScanError:
                pass

    def _wait_for_start(self):
        '''Wait for a software start event or hardware button press.'''
        while not self._stopping.is_set():
            if self._dev is not None:
                # Have a scanner connection.  First check hardware button.
                try:
                    if self._scan_button:
                        break
                except ScanError:
                    # Scanner went away
                    self._close()

                # Block on software start.
                if self._start.wait(0.1):
                    break

            else:
                # No scanner connection.  Don't try to make one, because
                # _setup() can take a while and runs with the GIL held.
                # Block on software start.
                if self._start.wait(1):
                    break

        # Reset start event
        self._start.clear()

    def _run_scan(self):
        # pylint chokes on SaneDev's dynamic attributes
        # pylint: disable=W0201
        with ScanError.sanitize():
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
            with ScanError.sanitize():
                while True:
                    self._dev.start()
                    yield self._dev.snap(True)
        except ScanError, e:
            if str(e) != 'Document feeder out of documents':
                raise
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
            with ScanError.sanitize():
                index = self._dev['scan'].index
                return bool(self._dev.__dict__['dev'].get_option(index))
        except KeyError:
            return False
