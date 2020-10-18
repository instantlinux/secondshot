MAXFAIL   ?= 100
PYPI_URL  ?= https://upload.pypi.org/legacy/
PYPI_USER ?= $(USER)
RRSYNC_URL = https://www.samba.org/ftp/unpacked/rsync/support/rrsync
VERSION   ?= $(shell grep -o '[0-9.]*' secondshot/_version.py)

VENV=python_env
VDIR=$(PWD)/$(VENV)

include Makefile.docker

analysis: flake8
test: pytest
package: bin/rrsync dist/secondshot-$(VERSION).tar.gz
publish: test_requirements package
	@echo Publishing python package
	(. $(VDIR)/bin/activate && \
	 twine upload --repository-url $(PYPI_URL) \
	   -u $(PYPI_USER) -p $(PYPI_PASSWORD) dist/*)

test_functional:
	@echo "Run Functional Tests - not yet implemented"

flake8: test_requirements
	@echo "Running flake8 code analysis"
	. $(VDIR)/bin/activate ; flake8 --exclude=python_env,check_rsnap.py \
	  secondshot tests \
	  --per-file-ignores='secondshot/alembic/versions/*:E501,E122,E128'
python_env: $(VDIR)/bin/python3

test_requirements: python_env
	@echo "Installing test requirements"
	(. $(VDIR)/bin/activate && \
	 pip install -r tests/requirements.txt)

$(VDIR)/bin/python3:
	@echo "Creating virtual environment"
	python3 -m venv --system-site-packages $(VENV)

pytest: test_requirements
	@echo "Running pytest unit tests"
	(. $(VDIR)/bin/activate && \
	 PYTHONPATH=. python3 -m pytest $(XARGS) ./tests/ \
	 --durations=10 \
	 --junitxml=./tests/results.xml \
	 --maxfail=$(MAXFAIL) \
	 --cov-report html \
	 --cov-report xml \
	 --cov-report term-missing \
	 --cov secondshot)

dist/secondshot-$(VERSION).tar.gz:
	@echo "Building package"
	pip show wheel >/dev/null; \
	if [ $$? -ne 0 ]; then \
	  (. $(VDIR)/bin/activate ; python setup.py sdist bdist_wheel); \
	else \
	  python setup.py sdist bdist_wheel ; \
	fi

bin/rrsync:
	@echo "Downloading rrsync"
	curl -sLo $@ $(RRSYNC_URL)
	chmod +x $@

clean:
	rm -rf build dist bin/rrsync secondshot/htmlcov *.egg-info \
	 .cache .pytest_cache tests/__pycache__
	find . -regextype egrep -regex '.*(coverage.xml|results.xml|\.pyc|~)' \
	 -exec rm -rf {} \;
wipe_clean: clean
	rm -rf python_env
