COVERAGE_CMD = coverage run manage.py test --noinput && coverage xml && coverage report

install:
	pip install -r requirements.txt -r requirements-dev.txt
.PHONY: install

test:
	python manage.py test --parallel
.PHONY: test

coverage:
	${COVERAGE_CMD}
.PHONY: coverage
