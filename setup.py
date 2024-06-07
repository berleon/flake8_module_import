import setuptools

extension = (
    "MIM = flake8_module_import.flake8_module_import:ModuleImportChecker"
)
setuptools.setup(
    name="flake8-module-import",
    version="0.1.0",
    description=(
        "A Flake8 plugin to enforce module imports instead of direct imports"
    ),
    author="Your Name",
    author_email="your.email@example.com",
    packages=["flake8_module_import"],
    install_requires=["flake8"],
    entry_points={
        "flake8.extension": [extension],
    },
    classifiers=[
        "Framework :: Flake8",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Quality Assurance",
    ],
)
