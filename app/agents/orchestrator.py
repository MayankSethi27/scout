"""
Orchestrator - Coordinates the entire agent pipeline.

RESPONSIBILITY:
The Orchestrator is the main entry point that coordinates all agents
and tools. It manages the execution flow from question to answer.

COMPLETE FLOW:
==============
1. User Question + Repo URL
        │
        ▼
2. PLANNER AGENT
   - Analyzes the question
   - Creates execution plan (which tools to use)
        │
        ▼
3. TOOL EXECUTION (based on plan)
   ┌─────────────────────────────────────┐
   │  a. CodeLoaderTool → Clone repo     │
   │  b. CodeIndexerTool → Index code    │
   │  c. SearchTool → Find relevant code │
   └─────────────────────────────────────┘
        │
        ▼
4. REASONING AGENT
   - Analyzes search results
   - Extracts insights about the code
        │
        ▼
5. ANSWER GENERATOR AGENT
   - Produces final human-readable answer
        │
        ▼
6. Return Answer to User
"""

from typing import Dict, Any, Optional

from app.agents.base import AgentContext, ToolResult, ToolType
from app.agents.planner import PlannerAgent
from app.agents.reasoning import ReasoningAgent
from app.agents.answer_generator import AnswerGeneratorAgent
from app.agents.tools.code_loader import CodeLoaderTool
from app.agents.tools.code_indexer import CodeIndexerTool
from app.agents.tools.search import SearchTool


class Orchestrator:
    """
    Coordinates the agent pipeline for code analysis.

    The orchestrator manages:
    - Agent initialization
    - Tool registration
    - Execution flow
    - Error handling
    """

    def __init__(
        self,
        llm_client: Any,
        embedding_service: Any,
        vector_store: Any,
        storage_path: str = "./repos"
    ):
        """
        Initialize the orchestrator with all dependencies.

        Args:
            llm_client: Client for LLM API calls
            embedding_service: Service for generating embeddings
            vector_store: Vector database for code storage
            storage_path: Path for storing cloned repositories
        """
        # Initialize agents
        self.planner = PlannerAgent(llm_client)
        self.reasoning = ReasoningAgent(llm_client)
        self.answer_generator = AnswerGeneratorAgent(llm_client)

        # Initialize tools
        self.tools: Dict[str, Any] = {
            ToolType.CODE_LOADER.value: CodeLoaderTool(storage_path),
            ToolType.CODE_INDEXER.value: CodeIndexerTool(
                embedding_service=embedding_service,
                vector_store=vector_store
            ),
            ToolType.SEARCH.value: SearchTool(
                embedding_service=embedding_service,
                vector_store=vector_store
            ),
        }

    async def analyze(
        self,
        question: str,
        repo_url: str,
        existing_context: Optional[AgentContext] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - analyze a codebase to answer a question.

        Args:
            question: User's question about the codebase
            repo_url: GitHub repository URL
            existing_context: Optional pre-existing context (for follow-ups)

        Returns:
            Dict with answer and execution metadata
        """
        # Create or use existing context
        if existing_context:
            context = existing_context
            context.question = question
        else:
            context = AgentContext(question=question, repo_url=repo_url)

        context.log(f"Orchestrator: Starting analysis for '{question[:50]}...'")

        try:
            # Step 1: Plan
            context = await self._run_planner(context)

            # Step 2: Execute tools
            context = await self._execute_tools(context)

            # Step 3: Reason about results
            context = await self._run_reasoning(context)

            # Step 4: Generate answer
            context = await self._generate_answer(context)

            context.log("Orchestrator: Analysis complete")

            return self._build_response(context)

        except Exception as e:
            context.add_error(f"Orchestration error: {str(e)}")
            return self._build_error_response(context, str(e))

    async def _run_planner(self, context: AgentContext) -> AgentContext:
        """Execute the planner agent."""
        context.log("Orchestrator: Running planner...")
        return await self.planner.run(context)

    async def _execute_tools(self, context: AgentContext) -> AgentContext:
        """Execute tools according to the plan."""
        if not context.plan or "steps" not in context.plan:
            context.add_error("No valid plan available")
            return context

        context.log("Orchestrator: Executing tool plan...")

        for step in context.plan["steps"]:
            tool_name = step.get("tool")
            params = step.get("params", {})

            if tool_name not in self.tools:
                context.add_error(f"Unknown tool: {tool_name}")
                continue

            tool = self.tools[tool_name]
            context.log(f"Orchestrator: Executing {tool_name}")

            result: ToolResult = await tool.execute(context, **params)

            if not result.success:
                context.add_error(f"{tool_name} failed: {result.error}")
                # Decide whether to continue or abort
                if tool_name == ToolType.CODE_LOADER.value:
                    # Can't continue without repo
                    break

        return context

    async def _run_reasoning(self, context: AgentContext) -> AgentContext:
        """Execute the reasoning agent."""
        context.log("Orchestrator: Running reasoning agent...")
        return await self.reasoning.run(context)

    async def _generate_answer(self, context: AgentContext) -> AgentContext:
        """Execute the answer generator agent."""
        context.log("Orchestrator: Generating answer...")
        return await self.answer_generator.run(context)

    def _build_response(self, context: AgentContext) -> Dict[str, Any]:
        """Build the final response object."""
        return {
            "success": True,
            "answer": context.final_answer,
            "metadata": {
                "question": context.question,
                "repo_url": context.repo_url,
                "search_results_count": len(context.search_results),
                "execution_log": context.execution_log,
                "errors": context.errors if context.errors else None
            }
        }

    def _build_error_response(
        self,
        context: AgentContext,
        error: str
    ) -> Dict[str, Any]:
        """Build an error response."""
        return {
            "success": False,
            "answer": None,
            "error": error,
            "metadata": {
                "question": context.question,
                "repo_url": context.repo_url,
                "execution_log": context.execution_log,
                "errors": context.errors
            }
        }

    async def analyze_with_context(
        self,
        question: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Continue analysis with existing context (follow-up questions).

        Skips loading and indexing if already done.
        """
        return await self.analyze(
            question=question,
            repo_url=context.repo_url,
            existing_context=context
        )
