from setuptools import setup
import os
from os import path
from gekkopy import version

name = "gekkopy"
description = "Python API for Gekko trading bot"
long_description = "See https://github.com/askmike/gekko for the trading bot."

this_directory = path.abspath(path.dirname(__file__))


def read(filename):
    with open(os.path.join(this_directory, filename), "rb") as f:
        return f.read().decode("utf-8")


if os.path.exists("README.md"):
    long_description = read("README.md")

packages = ["gekkopy"]
url = "https://github.com/mariushelf/gekkopy"
author = "Marius Helf"
author_email = "helfsmarius@gmail.com"
classifiers = [
    "Development Status :: 3",
    "Natural Language :: English",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
]

setup(
    name=name,
    description=description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=author,
    url=url,
    author_email=author_email,
    classifiers=classifiers,
    install_requires=["requests", "matplotlib", "pandas", "flask", "numpy"],
    version=version.__version__,
    packages=packages,
)
