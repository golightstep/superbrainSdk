from setuptools import setup, find_packages

setup(
    name="superbrain-fabric-sdk",
    version="5.1.0",
    packages=find_packages(),
    install_requires=["numpy", "faiss-cpu"],
    extras_require={
        "semantic": ["sentence-transformers"]
    },
    description="Superbrain Fabric v5.1 — The Soul Expansion: LCC, Memory History, Knowledge Graph & MIRROR stability.",
    author="Anispy",
)
