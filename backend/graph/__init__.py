"""DocuMind document-structure graph.

A *document-native* structural graph: edges are derived from the document's own
structure (reading order, page, heading path) at ingestion time.  Nothing here
extracts triples with a language model, and nothing here depends on an external
graph database — the edges are ordinary relational rows in PostgreSQL.

Relations
---------
``NEXT`` / ``PREV``
    Reading order between consecutive chunks.
``SAME_PAGE``
    Two chunks that share a page (both directions).
``SAME_SECTION``
    Two chunks under the same ``heading_path`` within a bounded window
    (both directions), so a section is navigable without becoming a clique.

The graph is additive: it never replaces the pgvector semantic path, it is
rebuilt (not appended to) whenever a document is reprocessed, and ownership
always flows ``edge -> chunk -> document -> user`` so one user can never
traverse another user's graph.
"""

from graph.models import DocumentGraphEdge

__all__ = ["DocumentGraphEdge"]
