What is this?
-------------

Scanvark is a simple batch scanning program designed for use with an
automatic document feeder.  It lets you scan many pages, reorder them,
and save groups of them to PDF files.  It is designed for high throughput.

There is no scanner configuration UI yet; configuration is done via a
text file specified on the command line.  See the examples/ directory
and scanvark/config.py.

Features
--------

- Supports hardware "scan" buttons
- Supports variable-length scanned pages
- Automatic page rotation and order reversal (configurable)
- Pages can be reordered by dragging and grouped with keyboard/mouse
- Scanning and PDF generation are done in the background

Requirements
------------

- Python Imaging Library (PIL)
- PIL SANE module (often packaged separately by distributions)
- NumPy
- PyGTK
- PyYAML
- ReportLab
