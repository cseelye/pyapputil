from setuptools import setup
import os

"""
Publish by building the package:
    python setup.py sdist
and then uploading:
    twine upload dist/<NAME>-<version>.tar.gz
"""

NAME = "pyapputil"

cwd = os.path.abspath(os.path.dirname(__file__))

def get_requirements(filename):
    return [ line for line in open(os.path.join(cwd, "requirements.txt")).readlines() \
            if line.strip() and not line.startswith("-") and not line.startswith("#") ]

setup(
    name = NAME,
    version = "__VERSION__",
    author = "Carl Seelye",
    author_email = "cseelye@gmail.com",
    description = "Tools for building CLI applications",
    license = "MIT",
    keywords = "cli arguments configuration logging signals threads time",
    packages = [NAME],
    url = "https://github.com/cseelye/{}".format(NAME),
    long_description = open(os.path.join(cwd, "README.rst")).read(),
    #long_description_content_type='text/markdown',
    install_requires = get_requirements("requirements.txt"),
    extras_requires = {
        "dev" : get_requirements("requirements-dev.txt")
    }
)

