import setuptools
import re

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

version = ""
with open("telegram/ext/commands/__init__.py") as f:
    version = re.search(
        r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE
    ).group(1)

if not version:
    raise RuntimeError("version is not set")

if version.endswith(("a", "b", "rc")):
    # append version identifier based on commit count
    try:
        import subprocess

        p = subprocess.Popen(
            ["git", "rev-list", "--count", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if out:
            version += out.decode("utf-8").strip()
        p = subprocess.Popen(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if out:
            version += "+g" + out.decode("utf-8").strip()
    except Exception:
        pass


setuptools.setup(
    name="telegram-ext-commands",
    version=version,
    author="Fyssion",
    author_email="fyssioncodes@gmail.com",
    description="Commands extension for python-telegram-bot based off of discord.py",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Fyssion/telegram-ext-commands",
    packages=["telegram.ext.commands",],
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
