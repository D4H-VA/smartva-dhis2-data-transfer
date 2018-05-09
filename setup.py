#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))

__version__ = ''
with open(os.path.join('datatransfer', '__version__.py')) as f:
    exec(f.read())

with open('README.rst', 'r') as f:
    readme = f.read()

setup(
    name='smartva-dhis2-data-transfer',
    version=__version__,
    description='DHIS2 to DHIS2 integration of Verbal Autopsy data',
    long_description=readme,
    author='Data For Health Initiative - Verbal Autopsy',
    url='https://github.com/D4H-VA/smartva-dhis2-data-transfer',
    keywords='smartva verbal autopsy dhis2 tariff odk',
    license='MIT',
    install_requires=[
        'requests',
        'logzero',
    ],
    packages=find_packages(),
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: MIT License',
        'License :: Other/Proprietary License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
)