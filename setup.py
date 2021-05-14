from setuptools import setup
import os

"""
Publish by building the package:
    python setup.py sdist
and then uploading:
    twine upload dist/<NAME>-<version>.tar.gz
"""

NAME = "pyapputil"
VERSION = "__VERSION__"

cwd = os.path.abspath(os.path.dirname(__file__))

def get_requirements(filename):
    return [ line for line in open(os.path.join(cwd, "requirements.txt")).readlines() \
            if line.strip() and not line.startswith("-") and not line.startswith("#") ]

assert VERSION != "__VERSION__", "You must set a version. Normally this would be automatically set to the git tag by the CICD system"
setup(
    name = NAME,
    version = VERSION,
    author = "Carl Seelye",
    author_email = "cseelye@gmail.com",
    description = "Tools for building CLI applications",
    license = "MIT",
    keywords = "cli arguments configuration logging signals threads time",
    packages = [NAME],
    url = "https://github.com/cseelye/{}".format(NAME),
    long_description = open(os.path.join(cwd, "README.md")).read(),
    long_description_content_type='text/markdown',
    install_requires = get_requirements("requirements.txt"),
    extras_requires = {
        "dev" : get_requirements("requirements-dev.txt")
    }
)
