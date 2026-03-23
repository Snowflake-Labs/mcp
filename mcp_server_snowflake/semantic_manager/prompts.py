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

get_semantic_view_context_prompt = """
Get AI context metadata from a semantic view: description (COMMENT),
SQL generation instructions (AI_SQL_GENERATION), question routing guidance
(AI_QUESTION_CATEGORIZATION), and extension data with sample values and
verified queries (WITH EXTENSION). Use to understand how to correctly
query a semantic view."""
