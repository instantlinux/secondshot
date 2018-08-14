PYPI_URL ?= https://nexus.instantlinux.net/repository/pypi/
PYPI_USER ?= svc_docker
RRSYNC_URL = https://www.samba.org/ftp/unpacked/rsync/support/rrsync
SSL_CHAIN ?= /usr/local/share/ca-certificates/instantlinux-ca.crt
VERSION ?= $(shell cat VERSION)

VENV=python_env
VDIR=$(PWD)/$(VENV)

analysis: flake8
test: pytest
package: etc/rrsync dist/secondshot-$(VERSION).tar.gz
publish: package
	@echo Publishing python package
	echo -n $(PYPI_PASSWORD) | keyring set $(PYPI_URL) $(PYPI_USER)
	twine upload --cert=$(SSL_CHAIN) --repository-url $(PYPI_URL) -u $(PYPI_USER) dist/*

test_functional:
	@echo "Run Functional Tests - not yet implemented"

flake8: test_requirements
	@echo "Running flake8 code analysis"
	(. $(VDIR)/bin/activate ; flake8 --exclude=python_env,secondshot/alembic/versions,check_rsnap.py \
	 secondshot tests)

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
	cd secondshot && \
	export PYTHONPATH=. && \
	(. $(VDIR)/bin/activate ; \
	py.test $(XARGS) ../tests/unittests/ \
	 --junitxml=../tests/unittests/results.xml \
	 --cov-report html \
	 --cov-report xml \
	 --cov-report term-missing \
	 --cov .) || echo "Ignoring results"

dist/secondshot-$(VERSION).tar.gz:
	@echo "Building package"
	python setup.py sdist bdist_wheel

etc/rrsync:
	@echo "Downloading rrsync"
	wget -q -O $@ $(RRSYNC_URL)
	chmod +x $@

clean:
	rm -rf build dist etc/rrsync secondshot/htmlcov python_env *.egg-info \
	 tests/unittests/__pycache__
	find . -regextype egrep -regex '.*(coverage.xml|results.xml|\.pyc|~)' \
	 -exec rm -rf {} \;
