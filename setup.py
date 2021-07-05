from setuptools import setup, find_packages

setup(
    name="git-glow",
    version="0.1.1",
    packages=find_packages(),
    author="Nicolas RAMY",
    author_email="nicolas.ramy@darkelda.com",
    license="MIT",
    description=(
        "A new git extension to use git flow "
        "branching model automatically with Jira and Github"
    ),
    long_description=open("README.md").read(),
    entry_points={
        "console_scripts": ["git-glow=glow.__main__:main"],
    },
    install_requires=[
        "colorama==0.4.4",
        "click==8.0.1",
        "emoji==1.2.0",
        "gitpython==3.1.12",
        "idna==2.10",
        "python-slugify==4.0.1",
        "requests==2.25.1",
        "semver==2.13.0",
        "termcolor==1.1.0",
        "urllib3[secure]==1.26.3",
    ],
    url="https://github.com/nicolasramy/git-glow",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Topic :: Terminals",
        "Topic :: Utilities",
    ],
)
