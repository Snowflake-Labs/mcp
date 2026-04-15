# Title

Unsafe manual sanitization in `STARTS WITH` filters should be replaced with parameterized handling or strict validation

# Summary

The Snowflake MCP server currently sanitizes `starts_with` values by stripping single quotes manually before interpolating the value into `SHOW ... STARTS WITH '...'` SQL fragments. This is weaker than parameterized handling and relies on ad hoc string cleanup for a user-controlled input.

# Affected files

- `mcp_server_snowflake/object_manager/tools.py`
- `mcp_server_snowflake/semantic_manager/tools.py`

# Current pattern

```python
sanitized_starts_with = starts_with.replace("'", "")
statement += f" STARTS WITH '{sanitized_starts_with}'"
```

# Why this is a problem

- It is manual sanitization on a user-controlled string.
- It is weaker than bind variables or a strict allowlist.
- It is easy for downstream forks to assume this path is safe and expand the accepted character set later.

# Recommended fix

- Prefer bind variables if Snowflake supports them for this clause.
- If the SQL dialect does not support binds for `STARTS WITH`, reject values outside a strict safe allowlist instead of mutating the string and continuing.

# Repro

Call any tool that reaches the `starts_with` path with punctuation-heavy input such as:

```text
foo'; DROP TABLE demo.public.t1;--
```

The current implementation mutates the string and still executes the query instead of rejecting the input outright.

# Notes

I patched a local fork by replacing the manual quote stripping with strict validation, but this should be fixed upstream so downstream deployments inherit the safer default.
