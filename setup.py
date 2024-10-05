import setuptools
import pathlib

setuptools.setup(
    name="n0va",
    version="1.0.0",
    author="LobeliaSecurity™",
    description="Python3 simple async Web(HTTP1.1) server that can handle get/post and loadbalancing",
    url="https://github.com/LobeliaSecurity/n0va",
    packages=[x.parent.as_posix() for x in pathlib.Path(".").glob("**/__init__.py")],
    install_requires=[
        "pyOpenSSL<=23.3.0",
    ],
    python_requires=">=3.10",
)
