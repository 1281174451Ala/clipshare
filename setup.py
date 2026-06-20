from setuptools import setup, find_packages

setup(
    name="clipshare",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "cryptography>=41.0.0",
        "pyperclip>=1.8.0",
        "Pillow>=10.0.0",
    ],
    extras_require={
        "windows": ["pywin32>=306"],
        "macos": ["pyobjc-framework-AppKit>=9.0", "pyobjc-framework-Cocoa>=9.0"],
    },
    entry_points={
        "console_scripts": [
            "clipshare=clipshare.cli:main",
        ],
    },
    python_requires=">=3.9",
)