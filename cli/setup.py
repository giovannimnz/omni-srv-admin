"""setup.py — omni CLI unificado.

Instalação:
    pip install -e cli/

Uso:
    omni --help
    omni fork-sync projects list
    omni fork-sync sync <project> --dry-run
    omni version
"""

from setuptools import setup, find_packages

setup(
    name="omni",
    version="0.2.3",
    author="Giovanni Muniz",
    author_email="munizgiovanni@hotmail.com",
    description="CLI unificada para administração de servidores e gestão de forks",
    # long_description omitido (README.md no root do repo)
    url="https://github.com/giovannimnz/omni-srv-admin",
    packages=find_packages(where="."),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "pg8000>=1.31.2",
        "PyYAML>=6.0.2",
    ],
    entry_points={
        "console_scripts": [
            "omni=omni.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
