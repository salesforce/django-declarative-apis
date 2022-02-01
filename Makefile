# Common variables
PYTHON=python
PACKAGE_DIR = django_declarative_apis
TEST_DIR = tests
EXAMPLE_DIR = example

TEST_CMD = ${PYTHON} manage.py test --parallel
TEST_WARNINGS_CMD = ${PYTHON} -Wa manage.py test
# see .coveragerc for settings
COVERAGE_CMD = coverage run manage.py test --noinput && coverage xml && coverage report
STATIC_CMD = flake8 ${PACKAGE_DIR} ${TEST_DIR} ${EXAMPLE_DIR} setup.py
VULN_STATIC_CMD = bandit -r -ii -ll -x ${PACKAGE_DIR}/migrations ${PACKAGE_DIR} 
FORMAT_CMD = black ${PACKAGE_DIR} ${TEST_DIR} ${EXAMPLE_DIR} setup.py
FORMATCHECK_CMD = ${FORMAT_CMD} --check


install:
	pip install --upgrade pip -r requirements.txt -r requirements-dev.txt
.PHONY: install

format:
	${FORMAT_CMD}
.PHONY: format

docs:
	pushd docs && DJANGO_SETTINGS_MODULE=tests.settings make html && popd
.PHONY: docs

readme:
	@pandoc -f rst -t markdown_github docs/source/overview.rst > README.md
	@echo "\n\n" >> README.md
	@pandoc -f rst -t markdown_github docs/source/quickstart.rst >> README.md
.PHONY: readme

# Test targets

# requires install and example-install
test-all: coverage vuln-static formatcheck example-coverage
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
