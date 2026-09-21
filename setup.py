from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="faker-grocery",
    version="0.3.1",
    description="A custom Faker provider for simulating supermarket/hypermarket products, aisles and departments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="jctranc",
    license="MIT",
    keywords="faker grocery supermarket hypermarket test data",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    package_data={"faker_grocery.data": ["*.json"]},
    install_requires=[
        "faker>=20.0.0",
    ],
    extras_require={
        "test": [
            "pytest",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
