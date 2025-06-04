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
    name="keylock-steganography-tool",
    version=get_version(),
    author="Your Name / KeyLock Team", # TODO: Replace with your name/team
    author_email="your.email@example.com", # TODO: Replace with your email
    description="Securely embed and extract API key-value pairs in PNG images using steganography and encryption.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/keylock-steganography-tool", # TODO: Replace with your GitHub repo URL
    packages=['keylock'], # Explicitly list our package
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License", # Ensure you add an MIT LICENSE file
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
    # If you had non-Python files inside your 'keylock' package (e.g. font files, templates)
    # you would need include_package_data=True and a MANIFEST.in file or package_data.
    # For this project, it's not strictly necessary as fonts are system-dependent.
)
