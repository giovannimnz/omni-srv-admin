"""setup.py — omni CLI unificado.

Instalação:
    pip install -e cli/

Uso:
    omni --help
    omni fork-sync projects list
    omni fork-sync sync <project> --dry-run
    omni version
"""

from pathlib import Path
import shutil

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.install_lib import install_lib as _install_lib


class build_py(_build_py):
    """Include the XRDP module assets in non-editable omni distributions."""

    def run(self) -> None:
        super().run()
        source = Path(__file__).resolve().parents[1] / "modules" / "xrdp-abnt2" / "files"
        destination = Path(self.build_lib) / "omni" / "assets" / "xrdp-abnt2"
        shutil.copytree(source, destination, dirs_exist_ok=True)


class install_lib(_install_lib):
    """Carry module assets into the final wheel's omni package directory."""

    def run(self) -> None:
        super().run()
        source = Path(__file__).resolve().parents[1] / "modules" / "xrdp-abnt2" / "files"
        destination = Path(self.install_dir) / "omni" / "assets" / "xrdp-abnt2"
        shutil.copytree(source, destination, dirs_exist_ok=True)

setup(
    name="omni",
    version="0.2.5",
    author="Giovanni Muniz",
    author_email="munizgiovanni@hotmail.com",
    description="CLI unificada para administração de servidores e gestão de forks",
    # long_description omitido (README.md no root do repo)
    url="https://github.com/giovannimnz/omni-srv-admin",
    packages=find_packages(where="."),
    cmdclass={"build_py": build_py, "install_lib": install_lib},
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
