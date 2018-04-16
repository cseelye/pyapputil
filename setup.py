from setuptools import setup
import os

NAME = "pyapputil"
setup(
    name = NAME,
    version = "1.0.5",
    author = "Carl Seelye",
    author_email = "cseelye@gmail.com",
    description = "Tools for building CLI applications",
    license = "MIT",
    keywords = "cli arguments configuration logging signals threads time",
    packages = [NAME],
    url = "https://github.com/cseelye/{}".format(NAME),
    long_description = open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    install_requires = open(os.path.join(os.path.dirname(__file__), "requirements.txt")).readlines()
)
