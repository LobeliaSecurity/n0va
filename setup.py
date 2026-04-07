import pathlib

import setuptools


def _dashboard_dist_files() -> list[str]:
    """Vite ビルド出力（dashboard/frontend/dist）を wheel に同梱する。"""
    dashboard_pkg = pathlib.Path(__file__).resolve().parent / "dashboard"
    dist_root = dashboard_pkg / "frontend" / "dist"
    if not dist_root.is_dir():
        return []
    return [
        str(p.relative_to(dashboard_pkg))
        for p in dist_root.rglob("*")
        if p.is_file()
    ]


_readme = pathlib.Path(__file__).resolve().parent / "README.md"
long_description = _readme.read_text(encoding="utf-8") if _readme.is_file() else ""

_dashboard_data = _dashboard_dist_files()
package_data = {"dashboard": _dashboard_data} if _dashboard_data else {}

setuptools.setup(
    name="n0va",
    version="1.0.0",
    author="LobeliaSecurity™",
    description=(
        "Asyncio toolkit: programmable Gate (TCP/TLS/HTTP-aware proxy), "
        "certificate utilities, optional dashboard, and HTTP/1.1 app surface."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LobeliaSecurity/n0va",
    license="MIT",
    project_urls={
        "Source": "https://github.com/LobeliaSecurity/n0va",
        "Issues": "https://github.com/LobeliaSecurity/n0va/issues",
    },
    packages=(
        setuptools.find_namespace_packages(include=["n0va*"])
        + setuptools.find_packages(include=["dashboard"])
    ),
    package_data=package_data,
    include_package_data=bool(package_data),
    python_requires=">=3.10",
    install_requires=[
        "pyOpenSSL>=23.0.0",
    ],
    extras_require={
        "dev": [
            "pytest",
        ],
    },
    entry_points={
        "console_scripts": [
            "n0va-dashboard=dashboard.run:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
