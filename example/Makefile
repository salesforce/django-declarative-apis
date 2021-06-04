# see .coveragerc for settings
COVERAGE_CMD = coverage run manage.py test --noinput && coverage xml && coverage report

example-tests: coverage
.PHONY: example-tests

coverage:
	${COVERAGE_CMD}
.PHONY: coverage