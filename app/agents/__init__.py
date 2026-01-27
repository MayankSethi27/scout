"""
Agent Architecture for GitHub Codebase Analyst
===============================================

FLOW OVERVIEW:
--------------
1. User submits a question about a GitHub repository
2. Planner Agent analyzes the question and creates an execution plan
3. Tools are executed in sequence:
   - CodeLoaderTool: Clones/loads the repository
   - CodeIndexerTool: Indexes code into vector store
   - SearchTool: Searches for relevant code snippets
4. Reasoning Agent analyzes search results and extracts insights
5. Answer Generator Agent produces the final human-readable response
6. Orchestrator coordinates the entire flow

ARCHITECTURE:
-------------
                    ┌─────────────────┐
                    │  User Question  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Planner Agent  │  ← Analyzes question, creates plan
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼─────┐ ┌──────▼─────┐ ┌──────▼─────┐
       │ CodeLoader │ │CodeIndexer │ │   Search   │  ← Tools
       │    Tool    │ │    Tool    │ │    Tool    │
       └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │ Reasoning Agent │  ← Analyzes results
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Answer Generator│  ← Produces final answer
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Final Answer   │
                    └─────────────────┘

USAGE:
------
    from app.agents import Orchestrator

    orchestrator = Orchestrator(
        llm_client=my_llm_client,
        embedding_service=my_embedding_service,
        vector_store=my_vector_store
    )

    result = await orchestrator.analyze(
        question="How does authentication work?",
        repo_url="https://github.com/user/repo"
    )

    print(result["answer"])
"""

from app.agents.base import BaseAgent, BaseTool, AgentContext, ToolResult
from app.agents.planner import PlannerAgent
from app.agents.reasoning import ReasoningAgent
from app.agents.answer_generator import AnswerGeneratorAgent
from app.agents.orchestrator import Orchestrator
from app.agents.tools import CodeLoaderTool, CodeIndexerTool, SearchTool

__all__ = [
    # Base classes
    "BaseAgent",
    "BaseTool",
    "AgentContext",
    "ToolResult",
    # Agents
    "PlannerAgent",
    "ReasoningAgent",
    "AnswerGeneratorAgent",
    "Orchestrator",
    # Tools
    "CodeLoaderTool",
    "CodeIndexerTool",
    "SearchTool",
]
