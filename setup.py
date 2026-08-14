from setuptools import setup, find_packages

setup(
    name='calculator-app',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'calc=calculator_app.cli:main',
        ],
    },
    install_requires=[],
    python_requires='>=3.7',
    description='A simple calculator supporting basic and some advanced operations.',
    author='Your Name',
    license='MIT',
)
