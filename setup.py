#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

setup(name='pynliner',
      version='0.5.1.13',
      description='Python CSS-to-inline-styles conversion tool for HTML using'
                  ' BeautifulSoup and cssutils',
      author='Tanner Netterville',
      author_email='tannern@gmail.com',
      packages=['pynliner'],
      install_requires=[
          'beautifulsoup4 >= 4.3.0, < 5',
          'cssutils >=0.9.7',
          'six==1.15.0',
          'lxml',
          'mock',
      ],
      provides=['pynliner'])
