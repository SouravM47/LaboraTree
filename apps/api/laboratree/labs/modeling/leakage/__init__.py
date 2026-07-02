"""Leakage Sentinel — the trust guard for every modelling pipeline.

Public surface is re-exported so `laboratree.labs.modeling.leakage` stays a stable import path.
"""

from .sentinel import LeakageSentinel, audit_leakage

__all__ = ["LeakageSentinel", "audit_leakage"]
