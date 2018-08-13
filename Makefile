PYPI_URL ?= https://nexus.instantlinux.net/repository/pypi/
PYPI_USER ?= svc_docker
SSL_CHAIN ?= /usr/local/share/ca-certificates/instantlinux-ca.crt
VERSION ?= $(shell cat VERSION)

VENV=python_env
VDIR=$(PWD)/$(VENV)

analysis: flake8
test: pytest
package: dist/secondshot-$(VERSION).tar.gz
publish: package
	@echo Publishing python package
	echo -n $(PYPI_PASSWORD) | keyring set $(PYPI_URL) $(PYPI_USER)
	twine upload --cert=$(SSL_CHAIN) --repository-url $(PYPI_URL) -u $(PYPI_USER) dist/*

test_functional:
	@echo "Run Functional Tests - not yet implemented"

flake8: test_requirements
	@echo "Running flake8 code analysis"
	(. $(VDIR)/bin/activate ; flake8 --exclude=python_env \
	 --exclude=check_rsnap.py lib tests)

python_env: $(VDIR)/bin/python

test_requirements: python_env
	@echo "Installing test requirements"
	(. $(VDIR)/bin/activate && \
	 pip install -r requirements/test.txt)

$(VDIR)/bin/python:
	@echo "Creating virtual environment"
	virtualenv --system-site-packages $(VENV)

pytest: test_requirements
	@echo "Running pytest unit tests"
	cd lib && \
	export PYTHONPATH=. && \
	(. $(VDIR)/bin/activate ; \
	py.test $(XARGS) ../tests/unittests/ \
	 --junitxml=../tests/unittests/results.xml \
	 --cov-report html \
	 --cov-report xml \
	 --cov-report term-missing \
	 --cov .)

dist/secondshot-$(VERSION).tar.gz:
	@echo "Building package"
	python setup.py sdist bdist_wheel

clean:
	rm -rf build dist lib/htmlcov python_env *.egg-info \
	 tests/unittests/__pycache__
	find . -regextype egrep -regex '.*(coverage.xml|results.xml|\.pyc|~)' \
	 -exec rm -rf {} \;
