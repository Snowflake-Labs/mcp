write_semantic_view_query_prompt = """
Writes a query statement to query a semantic view using DIMENSIONS, METRICS, and/or FACTS.
Supports optional WHERE, ORDER BY, and LIMIT clauses.
Query statement cannot combine FACTS and METRICS in same query.
Use tool if asked to create a query to query a semantic view."""

query_semantic_view_prompt = """
Writes and runs a statement to query a semantic view using DIMENSIONS, METRICS, and/or FACTS.
Supports optional WHERE, ORDER BY, and LIMIT clauses.
Query statement cannot combine FACTS and METRICS in same query.
Use tool if asked to query a semantic view directly."""
