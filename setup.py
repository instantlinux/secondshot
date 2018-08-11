import setuptools
from setuptools.command.test import test as TestCommand

__version__ = '0.9'


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
    packages=setuptools.find_packages(exclude=['tests', 'src']),
    include_package_data=True,
    test_suite='tests.unittests',
    cmdclass={'test': PyTest}
)
