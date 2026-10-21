"""Evaluation unit-test configuration.

Step 1.6K removed the draft live-lifecycle registry. No autouse registry reset or
proof-issuing fixture exists: Python state cannot supply missing authorization.
Database-free tests patch their own I/O boundaries explicitly.
"""
