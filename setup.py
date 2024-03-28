#!/usr/bin/env python3

from setuptools import setup

__version = "1.0.4"

setup(name="oc-client-provider",
        version=__version,
        description="Client provider",
        long_description="Provides client information from Django models",
        long_description_content_type="text/plain",
        license="Apache2.0",
        install_requires=[
            "oc-delivery-apps >= 11.2.9",
            "oc-orm-initializator >= 1.1.0",
            "flask",
            "gunicorn",
            "pytz",
            "pyyaml"],
      packages={"oc_client_provider"},
      python_requires=">=3.6")
