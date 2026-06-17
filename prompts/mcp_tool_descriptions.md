rag_index_folder:

Index documents from a local folder into the knowledge base. Scans for files with extensions .md, .txt, .py, .js, .ts, .json, .yaml, splits them into chunks, generates embeddings, and stores them for search. Call this FIRST before asking any questions if you need the agent to know about new documents.

Parameters:
  - path (required): Absolute or relative path to the folder to scan. Example: "./docs"
  - glob_pattern (optional): File pattern filter. Default "*" matches all supported types. Example: "*.md" for markdown only.

Call when: A user provides new documents, asks for information not yet answered, or says "index this folder".
Do NOT call when: The user already asked a question and wants an immediate answer (use rag_ask_question instead).

---

rag_ask_question:

Ask a question against the indexed knowledge base. This runs the full RAG pipeline: it rewrites the query for better search, finds relevant document chunks using hybrid (semantic + keyword) search, grades each chunk's relevance, and generates a final answer with source citations.

Parameters:
  - query (required): The natural-language question to answer. Be specific but concise. Example: "How is authentication configured?"

Call when: The user wants a direct answer to a question. This is the primary Q&A tool.
Do NOT call when: You need to inspect raw matching documents without an answer (use rag_find_relevant_docs) or the knowledge base has not been indexed yet (use rag_index_folder first).

---

rag_find_relevant_docs:

Search the knowledge base for relevant document chunks without generating a final answer. Returns ranked results sorted by hybrid search relevance (combining semantic vector similarity and BM25 keyword matching). Use this to browse, inspect, or verify which documents match a query.

Parameters:
  - query (required): The search query string. Example: "token expiration configuration"
  - top_k (optional): Number of results to return. Default 5, range 1–20. Example: 10

Call when: The user wants to see which documents match a query, compare sources, or verify retrieval quality before getting an answer.
Do NOT call when: The user wants a synthesized answer (use rag_ask_question) or needs to add new documents (use rag_index_folder).

---

rag_index_status:

Check the current state of the knowledge base index. Returns metadata including the number of files indexed, total chunks, collection name, and the timestamp of the last indexing operation. Use this to verify whether the knowledge base has content before searching.

Parameters: none

Call when: Before starting a search session to confirm the knowledge base is populated. After indexing to verify success. When the user asks "what's in the knowledge base" or "how many documents are indexed".
Do NOT call when: The user is actively asking a question or browsing results (use rag_ask_question or rag_find_relevant_docs instead).
