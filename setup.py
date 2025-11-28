from setuptools import setup, find_packages

setup(
    name="pytraders",
    version="0.0.2",
    description="Pacote para operações de backtest de carteira em índices da B3",
    author="Rodrigo Schneider",
    author_email="schneider.rs@gmail.com",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "selenium",
        #"chromium-chromedriver",
        "chromedriver-autoinstaller",
        "yfinance==0.2.66",
        "ta"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
)
