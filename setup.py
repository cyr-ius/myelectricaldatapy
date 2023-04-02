# -*- coding: utf-8 -*-
"""Provides setup."""
import os

from setuptools import find_packages, setup

# Method for retrieving the version is taken from the setup.py of pip itself:
# https://github.com/pypa/pip/blob/master/setup.py
here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="myelectricaldatapy",
    version="replace_by_workflow",
    packages=find_packages(),
    author="cyr-ius",
    author_email="cyr-ius@ipocus.net",
    description="Fetch Linky data from myelectricaldata.fr",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=["aiohttp>=3.8.1", "pandas==1.4.3", "voluptuous>=0.13.1"],
    license="GPL-3",
    include_package_data=True,
    url="https://github.com/cyr-ius/myelectricaldatapy/tree/master/myelectricaldatapy",
    keywords=["enedis", "linky", "async", "myelectricaldata"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: AsyncIO",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Home Automation",
    ],
)
