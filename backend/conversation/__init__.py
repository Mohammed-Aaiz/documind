"""Stateful conversation API (Phase C).

``POST /api/conversation/{session_id}/messages`` answers a question with
conversation memory held in Redis (or the reported in-process fallback).  The
text chat and the voice path both use :mod:`orchestration.service`, so a
conversation has exactly one history.
"""
