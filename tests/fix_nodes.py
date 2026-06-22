#!/usr/bin/env python3
"""Fix the inverted condition in src/graph/nodes.py line 576."""

path = "/home/zloooy/Учёба/AI в разработке/mcp-rag-knowlege-base/src/graph/nodes.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix line 576 (index 575): joined_len > limit → joined_len <= limit
lines[575] = lines[575].replace("joined_len > limit", "joined_len <= limit")

# Replace the old comment and add better one
lines[581] = (
    "            # Joined chunk exceeds the configured threshold — use it directly\n"
)
lines.insert(
    582,
    "            # to avoid sending megabytes of unrelated document text to the LLM.\n",
)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Fixed nodes.py successfully.")
