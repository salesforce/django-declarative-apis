# Common variables
PYTHON=python
PACKAGE_DIR = django_declarative_apis
TEST_DIR = tests
TEST_CMD = ${PYTHON} manage.py test --parallel
TEST_WARNINGS_CMD = ${PYTHON} -Wa manage.py test
# see .coveragerc for settings
COVERAGE_CMD = coverage run manage.py test --noinput && coverage xml && coverage report
STATIC_CMD = flake8 ${PACKAGE_DIR}
VULN_STATIC_CMD = bandit -r -ii -ll -x ${PACKAGE_DIR}/migrations ${PACKAGE_DIR} 
FORMATCHECK_CMD = black --check ${PACKAGE_DIR} ${TEST_DIR}


install:
	pip install -r requirements.txt -r requirements-dev.txt
.PHONY: install

format:
	black ${PACKAGE_DIR} ${TEST_DIR}
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

test-all: coverage static vuln-static
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
