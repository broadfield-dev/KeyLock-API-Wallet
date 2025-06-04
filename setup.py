# keylock-steganography-tool/setup.py
import os
import re
from setuptools import setup, find_packages

def get_version():
    with open(os.path.join("keylock", "__init__.py"), "r", encoding="utf-8") as f:
        version_match = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="keylock-api-wallet", # Changed name to reflect new repo name
    version=get_version(),
    author="Your Name / KeyLock Team", # TODO: Replace with your name/team
    author_email="your.email@example.com", # TODO: Replace with your email
    description="Securely embed and extract API key-value pairs in PNG images using steganography and encryption.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/user/KeyLock-API-Wallet", # UPDATED URL
    packages=['keylock'],
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security :: Cryptography",
        "Topic :: Multimedia :: Graphics",
        "Framework :: Gradio",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'keylock-app=keylock.app:main',
        ],
    },
)
