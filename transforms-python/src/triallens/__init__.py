"""TrialLens: governed clinical & omics data products.

Layers
------
raw       -> 14 source datasets landed as-is by Data Connection (strings only)
clean     -> typed, de-duplicated, pseudonymised per-source datasets
curated   -> integrated, analysis-ready datasets (cohort features, biomarker series, ...)
ontology  -> backing datasets for the 35 object types of the TrialLens ontology
"""

__version__ = "1.4.0"
