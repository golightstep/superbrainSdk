from setuptools import setup, find_packages

setup(
    name="superbrain",
    version="0.3.1",
    packages=find_packages(),
    install_requires=["numpy", "faiss-cpu"],
    extras_require={
        "semantic": ["sentence-transformers"]
    },
    description="Python SDK for Superbrain Distributed Memory",
    author="Anispy",
)
