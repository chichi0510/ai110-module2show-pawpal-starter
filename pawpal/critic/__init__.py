"""Self-critique layer (Phase 3).

Reviews RAG answers and Agent plans on three independent axes, aggregates the
scores into a single 0..1 confidence with a discrete level (high / medium /
low), and feeds the result back to both the UI (badge + collapse rules) and
the offline evaluation harness (AUROC calibration).
"""
