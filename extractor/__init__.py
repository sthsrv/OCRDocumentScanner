"""Extract the Findings section of a vulnerability report PDF."""
from .pipeline import convert_pdf

__all__ = ["convert_pdf"]
