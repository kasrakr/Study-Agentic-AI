"""Builds the study-assistant StateGraph.

START -> classify_intent
  smalltalk            -> respond_smalltalk -> END
  quiz / flashcards    -> generate_quiz / generate_flashcards -> END (selected documents only, never the web)
  otherwise            -> retrieve_documents -> grade_document_evidence
      sufficient       -> generate_answer -> END
      retry possible   -> rewrite_query -> retrieve_documents (bounded by max_retrieval_retries)
      otherwise        -> identify_missing_information -> web_search
                          -> grade_web_evidence -> generate_answer -> END
"""

from __future__ import annotations

from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import AgentDeps, AgentNodes
from app.agent.routing import route_after_classify, route_after_document_grade, route_after_rewrite
from app.agent.state import AgentState


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None):
    nodes = AgentNodes(deps)
    g = StateGraph(AgentState)

    g.add_node("classify_intent", nodes.classify_intent)
    g.add_node("respond_smalltalk", nodes.respond_smalltalk)
    g.add_node("retrieve_documents", nodes.retrieve_documents)
    g.add_node("grade_document_evidence", nodes.grade_document_evidence)
    g.add_node("rewrite_query", nodes.rewrite_query)
    g.add_node("identify_missing_information", nodes.identify_missing_information)
    g.add_node("web_search", nodes.web_search)
    g.add_node("grade_web_evidence", nodes.grade_web_evidence)
    g.add_node("generate_answer", nodes.generate_answer)
    g.add_node("generate_quiz", nodes.generate_quiz)
    g.add_node("generate_flashcards", nodes.generate_flashcards)

    g.add_edge(START, "classify_intent")
    g.add_conditional_edges("classify_intent", route_after_classify,
                            ["respond_smalltalk", "generate_quiz", "generate_flashcards", "retrieve_documents"])
    g.add_edge("retrieve_documents", "grade_document_evidence")
    g.add_conditional_edges(
        "grade_document_evidence",
        partial(route_after_document_grade, max_retries=deps.settings.max_retrieval_retries),
        ["generate_answer", "rewrite_query", "identify_missing_information"],
    )
    g.add_conditional_edges("rewrite_query", route_after_rewrite,
                            ["retrieve_documents", "identify_missing_information"])
    g.add_edge("identify_missing_information", "web_search")
    g.add_edge("web_search", "grade_web_evidence")
    g.add_edge("grade_web_evidence", "generate_answer")
    g.add_edge("generate_answer", END)
    g.add_edge("respond_smalltalk", END)
    g.add_edge("generate_quiz", END)
    g.add_edge("generate_flashcards", END)

    return g.compile(checkpointer=checkpointer)
