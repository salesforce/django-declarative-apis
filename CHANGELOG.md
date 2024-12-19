# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [Unreleased]
- [PR 156](https://github.com/salesforce/django-declarative-apis/pull/156) Update GitHub action versions
- [PR 162](https://github.com/salesforce/django-declarative-apis/pull/162) Fix Makefile install target

# [0.31.7]
- [PR 148](https://github.com/salesforce/django-declarative-apis/pull/148) chore: upgrade django 4.2 LTS

# [0.31.6]
- [PR 144](https://github.com/salesforce/django-declarative-apis/pull/144) Allow Dependabot to update dev dependencies
- [PR 143](https://github.com/salesforce/django-declarative-apis/pull/143) Testing: Replace `flake8` and `black` with `ruff`, add testing for Python 3.12, drop testing for Python 3.7
- [PR 146](https://github.com/salesforce/django-declarative-apis/pull/146) Add ExpandableGeneric filter type

# [0.31.5]
- [PR 141](https://github.com/salesforce/django-declarative-apis/pull/141) Clean up logging 
- [PR 138](https://github.com/salesforce/django-declarative-apis/pull/138) Docs: Correct imports in code-blocks
- [PR 139](https://github.com/salesforce/django-declarative-apis/pull/139) Docs: Correct documentation for default value of `required` on `field`
- [PR 140](https://github.com/salesforce/django-declarative-apis/pull/140) Docs: Add comment explaining why `dict`s don't have filters applied

# [0.31.4] - 2023-10-12
- [PR 137](https://github.com/salesforce/django-declarative-apis/pull/137) Finalize endpoints before dispatching async tasks

# [0.31.3] - 2023-09-30
- [PR 136](https://github.com/salesforce/django-declarative-apis/pull/136) Fix filter expansion for pydantic objects


# [0.31.2 = 2023-09-11]
- [PR 134](https://github.com/salesforce/django-declarative-apis/pull/134) Make filter caching work for all datatypes
- [PR 131](https://github.com/salesforce/django-declarative-apis/pull/131) Support non-utf8 request body

# [0.29.0] - 2023-08-16
- [PR 129](https://github.com/salesforce/django-declarative-apis/pull/129) Remove outdated HttpResponse wrapper 

# [0.28.0] - 2023-05-08
- [PR 127](https://github.com/salesforce/django-declarative-apis/pull/127) Add function and fake relations caching in filters

# [0.27.0] - 2023-04-27
- [PR 125](https://github.com/salesforce/django-declarative-apis/pull/125) Support resources that are not django models

# [0.26.0] - 2023-03-08
- [PR 124](https://github.com/salesforce/django-declarative-apis/pull/124) Add query caching in filters

# [0.25.3] - 2023-02-09
### Fixed
- [PR 122](https://github.com/salesforce/django-declarative-apis/pull/122) Handle malformed OAuth header

# [0.25.2] - 2023-01-24
### Fixed
- [PR 118](https://github.com/salesforce/django-declarative-apis/pull/118) Fix typo in docs
- [PR 120](https://github.com/salesforce/django-declarative-apis/pull/120) Fix correlation ID logging for deferred tasks

### Changed
- [PR 116](https://github.com/salesforce/django-declarative-apis/pull/XXX) Only run PR checks on `pull_request`

# [0.25.1] - 2022-12-19
### Fixed
- [PR 117](https://github.com/salesforce/django-declarative-apis/pull/117) Fix README specification in pyproject.toml

# [0.25.0] - 2022-12-19
### Added
- [PR 106](https://github.com/salesforce/django-declarative-apis/pull/106) Test against Python 3.11 in PR checks

### Fixed
- [PR 112](https://github.com/salesforce/django-declarative-apis/pull/112) Try again to use new ReadTheDocs config
- [PR 111](https://github.com/salesforce/django-declarative-apis/pull/111) ReadTheDocs only supports up to Python 3.8
- [PR 110](https://github.com/salesforce/django-declarative-apis/pull/110) Fix ReadTheDocs build by specifying python version differently
- [PR 108](https://github.com/salesforce/django-declarative-apis/pull/108) Fix ReadTheDocs documentation build with pyproject.toml

### Changed
- [PR 114](https://github.com/salesforce/django-declarative-apis/pull/114) Allow cryptography > 3.4.8
- [PR 113](https://github.com/salesforce/django-declarative-apis/pull/113) Require oauthlib >= 3.1.0
- [PR 109](https://github.com/salesforce/django-declarative-apis/pull/109) Update Github actions
- [PR 107](https://github.com/salesforce/django-declarative-apis/pull/107) Update to use pyproject.toml

# [0.24.0] - 2022-11-03
### Added
- [PR 101](https://github.com/salesforce/django-declarative-apis/pull/101) Allow Pydantic models as field types

### Fixed
- [PR 103](https://github.com/salesforce/django-declarative-apis/pull/103) Update contributing doc
- [PR 102](https://github.com/salesforce/django-declarative-apis/pull/102) Fix typos in docs and tests

### Changed
- [PR 100](https://github.com/salesforce/django-declarative-apis/pull/100) Improve `errors.py`

# [0.23.1] - 2022-05-17
### Fixed
- [PR 98](https://github.com/salesforce/django-declarative-apis/pull/98) Fix GitHub publish action

# [0.23.0] - 2022-05-17
### Added
- [PR 96](https://github.com/salesforce/django-declarative-apis/pull/96) Minor tweaks for ReadTheDocs integration
- [PR 94](https://github.com/salesforce/django-declarative-apis/pull/94) Add a Pull Request template/checklist to the repo
- [PR 92](https://github.com/salesforce/django-declarative-apis/pull/92) Run tests and static analysis as a PR check using GitHub actions
- [PR 83](https://github.com/salesforce/django-declarative-apis/pull/83) Allow Django 3
- [PR 82](https://github.com/salesforce/django-declarative-apis/pull/82) Allow Celery 5 by using `shared_task`

### Fixed
- [PR 95](https://github.com/salesforce/django-declarative-apis/pull/95) Fill in missing CHANGELOG entries
- [PR 90](https://github.com/salesforce/django-declarative-apis/pull/90) Fix `BoundEndpointManager` `get_response` saves
- [PR 89](https://github.com/salesforce/django-declarative-apis/pull/89) Fix save behavior for Django 3 and drop Django 2 support

### Changed
- [PR 93](https://github.com/salesforce/django-declarative-apis/pull/93) Remove spaces in name of `test` GitHub Action
- [PR 91](https://github.com/salesforce/django-declarative-apis/pull/91) Update black, flake8, and coverage and include flake8 in make test-all
- [PR 86](https://github.com/salesforce/django-declarative-apis/pull/86) Don't drop support for Django 2.2 until consumers catch up
- [PR 85](https://github.com/salesforce/django-declarative-apis/pull/85) Update easy dev requirements (black, coverage, flake8, pyyaml)
- [PR 84](https://github.com/salesforce/django-declarative-apis/pull/84) Tweak Makefiles for use with `example` directory
- [PR 81](https://github.com/salesforce/django-declarative-apis/pull/81) Upgrade pip as part of `make install`
- [PR 69](https://github.com/salesforce/django-declarative-apis/pull/69), [PR 70](https://github.com/salesforce/django-declarative-apis/pull/70), [PR 71](https://github.com/salesforce/django-declarative-apis/pull/71), [PR 73](https://github.com/salesforce/django-declarative-apis/pull/73), [PR 76](https://github.com/salesforce/django-declarative-apis/pull/76), [PR 77](https://github.com/salesforce/django-declarative-apis/pull/77), [PR 78](https://github.com/salesforce/django-declarative-apis/pull/78), [PR 79](https://github.com/salesforce/django-declarative-apis/pull/79) Work on GitHub actions

# [0.22.3] - 2021-11-18
### Added 
- [PR 59](https://github.com/salesforce/django-declarative-apis/pull/59) Add test cases for example app's model and responses

### Fixed
- [PR 55](https://github.com/salesforce/django-declarative-apis/pull/55) Backwards compatibility fix for field expansion headers, update example app

### Changed
- [PR 52](https://github.com/salesforce/django-declarative-apis/pull/52) Update cryptography and coverage dependencies
- [PR 53](https://github.com/salesforce/django-declarative-apis/pull/53) Update dev dependencies: flake8, bandit, ipython
- [PR 54](https://github.com/salesforce/django-declarative-apis/pull/54) Remove unneeded `mock` dependency
- [PR 56](https://github.com/salesforce/django-declarative-apis/pull/56) Add Python 3.8 and 3.9 to Travis CI testing
- [PR 58](https://github.com/salesforce/django-declarative-apis/pull/58) Update black dev dependency

# [0.22.2] - 2020-08-11
### Fixed
- [PR 48](https://github.com/salesforce/django-declarative-apis/pull/48) Apply filters to dict values

# [0.22.1] - 2020-08-11
### Fixed
- [PR 46](https://github.com/salesforce/django-declarative-apis/pull/46) Fix travis config

# [0.22.0] - 2020-08-11
### Added
- [PR 45](https://github.com/salesforce/django-declarative-apis/pull/45) Add optional deferrable tasks

# [0.21.0]
### Added
- [PR 42](https://github.com/salesforce/django-declarative-apis/pull/42) Add inst_field_name to expandable fields
### Changed
- [PR 39](https://github.com/salesforce/django-declarative-apis/pull/39) Add long_description to setup 
- [PR 40](https://github.com/salesforce/django-declarative-apis/pull/40) Remove use of root logger

# [0.20.0] - 2020-03-09
### Added
- [PR 21](https://github.com/salesforce/django-declarative-apis/pull/21) Add Makefile targets for Black formatter
- [PR 22](https://github.com/salesforce/django-declarative-apis/pull/22) Format code with Black
- [PR 34](https://github.com/salesforce/django-declarative-apis/pull/34) Test coverage, vulnerabilities, and format with TravisCI

### Changed
- [PR 28](https://github.com/salesforce/django-declarative-apis/pull/28) Require Django 2.2

### Fixed
- [PR 18](https://github.com/salesforce/django-declarative-apis/pull/18) Bump PyYaml dev requirement version
- [PR 19](https://github.com/salesforce/django-declarative-apis/pull/19) Bump required Django patch version
- [PR 20](https://github.com/salesforce/django-declarative-apis/pull/20) Fix deprecation warnings
- [PR 20](https://github.com/salesforce/django-declarative-apis/pull/20) Fix incorrect version number in docs and .bumpversion
- [PR 23](https://github.com/salesforce/django-declarative-apis/pull/23) Fix some flake8 warnings
- [PR 26](https://github.com/salesforce/django-declarative-apis/pull/26) Use yaml.safe_load in test
- [PR 27](https://github.com/salesforce/django-declarative-apis/pull/27) Fix more flake8 warnings
- [PR 29](https://github.com/salesforce/django-declarative-apis/pull/29) Ignore unused imports in example
- [PR 33](https://github.com/salesforce/django-declarative-apis/pull/33) Fix filters for classes with mixins

# [0.19.3] - 2020-02-04
- Increase celery version range

# [0.19.2] - 2020-02-04
- [PR 15](https://github.com/salesforce/django-declarative-apis/pull/15) Make newly added settings optional

# [0.19.1] - 2020-02-04
### Fixed
- [PR 14](https://github.com/salesforce/django-declarative-apis/pull/14) Retry async tasks if kombu.exceptions.OperationalError is encounterer
- [PR 14](https://github.com/salesforce/django-declarative-apis/pull/14) Added DECLARATIVE_ENDPOINT_TASKS_FORCE_SYNCHRONOUS. This allows users to entirely skip asynchronous task processing if needed.
- [PR 14](https://github.com/salesforce/django-declarative-apis/pull/14) Added DECLARATIVE_ENDPOINT_TASKS_SYNCHRONOUS_FALLBACK. This allows asynchronous tasks to automatically fall back to processing synchronously should asynchronous processing fail.

# [0.19.0] - 2020-01-07
### Added
- [PR 12](https://github.com/salesforce/django-declarative-apis/pull/12) Added support for logging correlation ids in deferred tasks.

## [0.18.5] - 2019-11-13
### Fixed
- Fix to allow for most recent celery version ([PR](https://github.com/salesforce/django-declarative-apis/pull/10))
- Fixed Django 2.0 deprecation warnings ([PR](https://github.com/salesforce/django-declarative-apis/pull/9))
