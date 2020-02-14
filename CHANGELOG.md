# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

# []
### Fixed
- [PR 18](https://github.com/salesforce/django-declarative-apis/pull/18) Bump PyYaml dev requirement version

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
