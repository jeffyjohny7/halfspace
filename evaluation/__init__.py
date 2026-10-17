"""Evaluation: the ONLY package allowed to read data/hidden.

It scores what the analytics and agents claim against the hidden answer key.
Nothing in analytics/, mcp_server/ or the agents may import from here at runtime.
"""
