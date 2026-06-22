---
description: Implements Python MCP server
mode: subagent
model: neuraldeep/qwen3.6-35b-a3b-noreason
permission:
    edit:
        "*": deny
        "pyproject.toml": allow
        "src/mcp_server/*": allow
        "tests/*": allow
    read:
        "*": allow
        ".env": deny
    bash:
        "*": allow
        "git*": deny
        "cat*": deny
        "head*": deny
        "sed*": deny
        "echo*": deny
        "python3 -c*": deny
        "python3 <<*": deny
        "python -c*": deny
        "python <<*": deny
    grep: allow
    glob: allow
    question: deny
    skill:
        "python-mcp-server-generator": allow
        "pydantic": allow
        "pytest-patterns": allow
---
You are programmer working on MCP Python application interface. Follow Zen of Python principles.
Use uv for package management.
Always respond with task status, even in case of failure explain your problem.