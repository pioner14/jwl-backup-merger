from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="jwl-backup-merger",
    version="1.0.0",
    author="AI Assistant",
    author_email="assistant@example.com",
    description="Инструмент для объединения нескольких бэкапов JW Library в один инкрементарный бэкап",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/jwl-backup-merger",
    py_modules=["jwl_backup_merger"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "jwl-backup-merger=jwl_backup_merger:main",
        ],
    },
)