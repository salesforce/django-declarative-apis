#!/usr/bin/env python
#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import setuptools
from os import path

with open(path.join(path.dirname(__file__), "requirements.txt")) as requirements_file:
    requirements = requirements_file.read().split()

setuptools.setup(
    name="django-declarative-apis",
    version="0.20.0",  # set by bumpversion
    author="Drew Shafer",
    url="https://salesforce.com",
    description="Simple, readable, declarative APIs for Django",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP",
    ],
    packages=setuptools.find_packages(),
    test_suite="tests",
    install_requires=requirements,
)
