import io
import os.path
import setuptools
from setuptools.command.test import test as TestCommand

from secondshot._version import __version__

__long_desc__ = io.open(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'README.md'), encoding='utf-8').read()


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--junitxml', 'tests/test-result.xml',
            '--cov-report', 'term-missing',
            '--cov-report', 'html',
            '--cov-report', 'xml']
        self.test_suite = True

    def run_tests(self):
        import pytest
        pytest.main(self.test_args)


setuptools.setup(
    version=__version__,
    name='secondshot',
    description='Linux-based backup utility',
    long_description=__long_desc__,
    long_description_content_type='text/markdown',
    keywords='backup rsync rsnapshot',
    author='Rich Braun',
    author_email='richb@instantlinux.net',
    url='https://github.com/instantlinux/secondshot',
    entry_points={
      'console_scripts': ['secondshot=secondshot.main:main']
    },
    scripts=['bin/check_rsnap.py', 'bin/cron-secondshot.sh', 'bin/rrsync'],
    packages=setuptools.find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=[
        'alembic>=1.11.2',
        'docopt>=0.6.2',
        'pymysql<1.0',
        'sqlalchemy<1.4'],
    python_requires='>=3.8',
    test_suite='tests.unittests',
    cmdclass={'test': PyTest},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Topic :: System :: Archiving :: Backup',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11'
    ]
)
