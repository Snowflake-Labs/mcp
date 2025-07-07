FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

ENV UV_LINK_MODE=copy

COPY docker/notebook/entrypoint.sh /entrypoint.sh

# Create virtual environment and install packages
RUN uv venv .venv
RUN uv pip install marimo snowflake-connector-python fastmcp

ENV PATH="/app/.venv/bin:$PATH"

# Create Snowflake config directory
RUN mkdir -p /root/.snowflake

RUN chmod +x /entrypoint.sh

WORKDIR /app/notebooks

EXPOSE 2718

ENTRYPOINT ["/entrypoint.sh"]
