"""Deterministic safety rules layered on top of every AI output.

These modules are pure-Python rule sets, not LLM calls — that is the
whole point: AI may reason, but a hard list of unsafe items always has
the final word before something reaches the user (or a real Pet's task list).
"""
