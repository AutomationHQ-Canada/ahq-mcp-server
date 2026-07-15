FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
# Served as MCP prompts by src/prompts.py — hosted clients get the curated workflows too.
COPY skills ./skills

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Slice 9j: bake Chromium (+ OS deps, needs root) into the image at BUILD time so the
# playwright package and browser build are version-locked together — the pip-vs-browser
# mismatch class becomes impossible for hosted users. Shared path readable by appuser;
# must be a runtime ENV so the server process finds the browsers.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright

RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["ahq-mcp-http"]
