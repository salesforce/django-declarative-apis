# Common variables
PYTHON=python
PACKAGE_DIR = django_declarative_apis
TEST_DIR = tests
EXAMPLE_DIR = example

TEST_CMD = ${PYTHON} manage.py test --parallel
TEST_WARNINGS_CMD = ${PYTHON} -Wa manage.py test
# see .coveragerc for settings
COVERAGE_CMD = coverage run manage.py test --noinput && coverage xml && coverage report
STATIC_CMD = ruff check .
VULN_STATIC_CMD = bandit -r -ii -ll -x ${PACKAGE_DIR}/migrations ${PACKAGE_DIR} 
FORMAT_CMD = ruff format .
FORMATCHECK_CMD = ${FORMAT_CMD} --check


install:
	pip install --upgrade pip install .[dev]
.PHONY: install

format:
	${FORMAT_CMD}
.PHONY: format

docs:
	DJANGO_SETTINGS_MODULE=tests.settings $(MAKE) -C docs html SPHINXOPTS="-W"
.PHONY: docs

readme:
	@pandoc -f rst -t markdown_github docs/source/overview.rst > README.md
	@echo "\n\n" >> README.md
	@pandoc -f rst -t markdown_github docs/source/quickstart.rst >> README.md
.PHONY: readme

# Test targets

test-all: coverage static vuln-static formatcheck docs
.PHONY: test-all

test:
	${TEST_CMD}
.PHONY: test

test-warnings:
	${TEST_WARNINGS_CMD}
.PHONY: test-warnings

coverage:
	${COVERAGE_CMD}
.PHONY: coverage

static:
	${STATIC_CMD}
.PHONY: static

vuln-static:
	${VULN_STATIC_CMD}
.PHONY: vuln-static

formatcheck:
	${FORMATCHECK_CMD}
.PHONY: formatcheck

example-install:
	$(MAKE) -C example install

example-test:
	$(MAKE) -C example test

example-coverage:
	$(MAKE) -C example coverage
