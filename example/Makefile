COVERAGE_CMD = coverage run manage.py test --noinput && coverage xml && coverage report

install:
	pip install -r requirements.txt
.PHONY: install

example-tests: coverage
.PHONY: example-tests

coverage:
	${COVERAGE_CMD}
.PHONY: coverage