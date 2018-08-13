import os.path
import setuptools
from setuptools.command.test import test as TestCommand

__version__ = open(os.path.join(os.getcwd(), 'VERSION')).read()


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--junitxml',
            'tests/test-result.xml',
            '--cov-report',
            'term-missing',
            '--cov-report',
            'html',
            '--cov-report',
            'xml',
            '--cov',
            'app']
        self.test_suite = True

    def run_tests(self):
        import pytest
        pytest.main(self.test_args)


setuptools.setup(
    version=__version__,
    name='secondshot',
    description='Linux-based backup utility',
    author='Rich Braun',
    author_email='richb@instantlinux.net',
    url='https://github.com/instantlinux/secondshot',
    console_scripts=['secondshot=lib.secondshot.main'],
    packages=setuptools.find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=[
        'alembic',
        'docopt',
        'sqlalchemy'],
    python_requires='>=2.7.3',
    test_suite='tests.unittests',
    cmdclass={'test': PyTest}
)
