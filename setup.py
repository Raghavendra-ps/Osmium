from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in ai_assistant/__init__.py
from ai_assistant import __version__ as version

setup(
	name="ai_assistant",
	version=version,
	description="AI Assistant for ERPNext with intelligent chat and database interactions",
	author="ERPNext",
	author_email="support@erpnext.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)