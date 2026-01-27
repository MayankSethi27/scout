"""
Reasoning Agent - Analyzes search results and extracts insights.

RESPONSIBILITY:
The Reasoning Agent takes raw search results (code snippets) and
analyzes them to understand how they relate to the user's question.
It identifies patterns, relationships, and key insights.

FLOW:
1. Receive search results (code snippets with metadata)
2. Analyze code in context of the original question
3. Extract key insights and relationships
4. Output structured reasoning for the Answer Generator
"""

from typing import Any

from app.agents.base import BaseAgent, AgentContext, AgentRole


REASONING_SYSTEM_PROMPT = """You are a code analysis expert. Your job is to analyze
code snippets and extract insights relevant to the user's question.

Given:
- A question about a codebase
- Search results (code snippets with file paths)

Your task:
1. Analyze how each code snippet relates to the question
2. Identify patterns, relationships, and key logic
3. Note important function names, classes, and data flows
4. Summarize your findings in a structured way

Output format:
- Key Findings: Main insights relevant to the question
- Code Analysis: Explanation of relevant code sections
- Relationships: How different parts of the code connect
- Confidence: How confident you are in your analysis (high/medium/low)
"""


class ReasoningAgent(BaseAgent):
    """
    Analyzes search results to extract insights.

    This agent bridges the gap between raw code snippets and
    meaningful answers by understanding the code's purpose
    and how it relates to the user's question.
    """

    role = AgentRole.REASONING

    def __init__(self, llm_client: Any):
        super().__init__(llm_client)

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Analyze search results and extract insights.

        Args:
            context: Contains question and search_results

        Returns:
            Context updated with reasoning_output
        """
        context.log("Reasoning: Analyzing search results...")

        if not context.search_results:
            context.reasoning_output = "No code snippets found to analyze."
            context.add_error("No search results available for reasoning")
            return context

        # Build prompt with search results
        prompt = self._build_prompt(context)

        # Get analysis from LLM
        reasoning = await self._call_llm(prompt, REASONING_SYSTEM_PROMPT)

        context.reasoning_output = reasoning
        context.log("Reasoning: Analysis complete")

        return context

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the reasoning prompt with search results."""
        # Format search results for the prompt
        results_text = self._format_search_results(context.search_results)

        return f"""
Question: {context.question}

Repository: {context.repo_url}

Search Results:
{results_text}

Analyze these code snippets and explain how they relate to the question.
Focus on understanding the code's purpose and behavior.
"""

    def _format_search_results(self, results: list) -> str:
        """Format search results into readable text."""
        if not results:
            return "No results found."

        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""
--- Result {i} ---
File: {result.get('file_path', 'Unknown')}
Score: {result.get('score', 'N/A')}

```
{result.get('content', 'No content')}
```
""")
        return "\n".join(formatted)
