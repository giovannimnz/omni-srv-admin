"""setup.py — fork-sync CLI unificado.

Instalação:
    pip install -e cli/

Uso:
    fork-sync --help
    fork-sync projects list
    fork-sync sync aionui --dry-run
    fork-sync deploy atius-router
    fork-sync repl  # modo interativo
"""

from setuptools import setup, find_packages

setup(
    name="fork-sync",
    version="1.3.0",
    author="Giovanni Muniz",
    author_email="munizgiovanni@hotmail.com",
    description="CLI unificado para gestão de forks: sync, deploy, versionamento, submodules",
    long_description=open("../README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/giovannimnz/fork-sync",
    packages=find_packages(where="."),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    # CLI movida para omni (
    # entry_points={
    #     "console_scripts": [
    #         "fork-sync=fork_sync.cli:main",
    #     ],
    # },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10+",
    ],
)
