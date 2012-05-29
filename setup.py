#!/usr/bin/env python

from distutils.core import setup

setup(
    name='Scanvark',
    description='A simple batch scanning program',
    author='Benjamin Gilbert',
    author_email='bgilbert@backtick.net',
    url='https://github.com/bgilbert/scanvark',
    packages=['scanvark'],
    scripts=['tools/scanvark'],
    license='GPLv2',
)
