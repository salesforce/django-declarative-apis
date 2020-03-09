# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

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
