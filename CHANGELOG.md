# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

# [0.19.1] -
### Fixed
- [PR 14](https://github.com/salesforce/django-declarative-apis/pull/14) Retry async tasks if kombu.exceptions.OperationalError is encounterer
- [PR 14](https://github.com/salesforce/django-declarative-apis/pull/14) Added DECLARATIVE_ENDPOINT_FORCE_SYNCHRONOUS_TASKS. This allows users to entirely skip asynchronous task processing if needed.

# [0.19.0] - 2020-01-07
### Added
- [PR 12](https://github.com/salesforce/django-declarative-apis/pull/12) Added support for logging correlation ids in deferred tasks.

## [0.18.5] - 2019-11-13
### Fixed
- Fix to allow for most recent celery version ([PR](https://github.com/salesforce/django-declarative-apis/pull/10))
- Fixed Django 2.0 deprecation warnings ([PR](https://github.com/salesforce/django-declarative-apis/pull/9))
