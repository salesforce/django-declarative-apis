#!/usr/bin/env python
#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import setuptools
from os import path


HERE = path.dirname(__file__)

with open(path.join(HERE, "requirements.txt")) as requirements_file:
    requirements = requirements_file.read().split()

with open(path.join(HERE, "README.md")) as readme_file:
    long_description = readme_file.read()

setuptools.setup(
    name="django-declarative-apis",
    version="0.22.2",  # set by bumpversion
    author="Drew Shafer",
    url="https://salesforce.com",
    description="Simple, readable, declarative APIs for Django",
    long_description=long_description,
    long_description_content_type="text/markdown",
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
