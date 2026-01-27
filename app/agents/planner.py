"""
Planner Agent - Analyzes questions and creates execution plans.

RESPONSIBILITY:
The Planner is the "brain" that decides HOW to answer a question.
It analyzes the user's question and creates a step-by-step plan
of which tools to use and in what order.

FLOW:
1. Receive user question and repo URL
2. Analyze what information is needed
3. Create execution plan (list of tool calls)
4. Return plan for orchestrator to execute
"""

import json
from typing import Any

from app.agents.base import BaseAgent, AgentContext, AgentRole, ToolType


# System prompt that defines the planner's behavior
PLANNER_SYSTEM_PROMPT = """You are a code analysis planner. Your job is to create
execution plans for answering questions about GitHub repositories.

Available tools:
1. code_loader - Clones/loads a repository to local storage
2. code_indexer - Indexes code files into a searchable vector store
3. search - Searches for relevant code using semantic similarity

Given a question, output a JSON plan with this structure:
{
    "analysis": "Brief analysis of what the question needs",
    "steps": [
        {"tool": "tool_name", "params": {}, "reason": "why this step"}
    ]
}

Rules:
- Always start with code_loader if repo isn't loaded
- Always index before searching
- Use search to find relevant code snippets
- Keep plans simple and focused
"""


class PlannerAgent(BaseAgent):
    """
    Creates execution plans based on user questions.

    The planner analyzes what the user wants to know and determines
    the sequence of tool calls needed to gather the required information.
    """

    role = AgentRole.PLANNER

    def __init__(self, llm_client: Any):
        super().__init__(llm_client)

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Analyze question and create execution plan.

        Args:
            context: Contains question and repo_url

        Returns:
            Context updated with execution plan
        """
        context.log(f"Planner: Analyzing question - {context.question[:50]}...")

        # Build the prompt for the LLM
        prompt = self._build_prompt(context)

        # Get plan from LLM
        response = await self._call_llm(prompt, PLANNER_SYSTEM_PROMPT)

        # Parse the plan
        plan = self._parse_plan(response, context)
        context.plan = plan

        context.log(f"Planner: Created plan with {len(plan['steps'])} steps")
        return context

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the planning prompt."""
        return f"""
Question: {context.question}
Repository: {context.repo_url}
Repo loaded: {context.repo_path is not None}
Repo indexed: {context.is_indexed}

Create an execution plan to answer this question.
"""

    def _parse_plan(self, response: str, context: AgentContext) -> dict:
        """
        Parse LLM response into execution plan.

        Falls back to default plan if parsing fails.
        """
        try:
            # Try to extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            context.add_error("Failed to parse planner response, using default plan")

        # Default plan if LLM response can't be parsed
        return self._get_default_plan(context)

    def _get_default_plan(self, context: AgentContext) -> dict:
        """
        Generate a sensible default plan.

        Used when LLM response can't be parsed or as fallback.
        """
        steps = []

        # Step 1: Load repo if not loaded
        if not context.repo_path:
            steps.append({
                "tool": ToolType.CODE_LOADER.value,
                "params": {"repo_url": context.repo_url},
                "reason": "Repository needs to be cloned first"
            })

        # Step 2: Index if not indexed
        if not context.is_indexed:
            steps.append({
                "tool": ToolType.CODE_INDEXER.value,
                "params": {},
                "reason": "Code needs to be indexed for search"
            })

        # Step 3: Always search
        steps.append({
            "tool": ToolType.SEARCH.value,
            "params": {"query": context.question},
            "reason": "Search for relevant code snippets"
        })

        return {
            "analysis": "Default plan: load, index, and search",
            "steps": steps
        }
