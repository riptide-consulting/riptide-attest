"""Riptide Attest: deterministic compliance verification.

Package layout mirrors the trust boundary:

    attest/engine/    pure, deterministic, no clock, no network, no model.
    attest/           everything else: collection (holds the clock),
                      audit logging, the gated publisher, and the model
                      layer (triage, compiler, explainer) that runs only
                      at authoring time.
"""

__version__ = "1.0.0"
