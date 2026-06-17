"""Graph construction for the Corrective RAG LangGraph pipeline.

This module assembles nodes, edges, and conditional routing into a
compiled ``StateGraph`` ready to be invoked with ``app.invoke(...)``.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .edges import should_broaden
from .nodes import (
    broaden,
    generate_answer,
    grade_chunks,
    retrieve,
    rewrite_query,
)
from .state import RAGState


def build_graph() -> StateGraph:
    """Build and compile the Corrective RAG LangGraph state graph.

    Topology::

        START --> rewrite_query --> retrieve --> grade_chunks
                                                   |
                     +--< enough relevant? >-------+
                     |                             |
               yes   v            no (budget left) v
              generate_answer             broaden_and_retry
                     |                             |
                     +-------------> retrieve <----+
                     |
                     v
                    END

    Returns
    -------
    StateGraph
        A compiled LangGraph graph ready for invocation.
    """
    graph = StateGraph(RAGState)

    # --- Nodes -----------------------------------------------------------
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_chunks", grade_chunks)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("broaden_and_retry", broaden)

    # --- Edges -----------------------------------------------------------
    graph.add_edge(START, "rewrite_query")
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("retrieve", "grade_chunks")

    # Conditional routing after grading
    graph.add_conditional_edges(
        "grade_chunks",
        should_broaden,
        {
            "broaden_and_retry": "broaden_and_retry",
            "generate_answer": "generate_answer",
        },
    )

    # Broaden loops back to retrieve for re-search
    graph.add_edge("broaden_and_retry", "retrieve")

    # Finish
    graph.add_edge("generate_answer", END)

    return graph
