"""
Answer Generator Agent - Produces final human-readable answers.

RESPONSIBILITY:
The Answer Generator takes the reasoning analysis and produces
a clear, helpful answer for the user. It focuses on being:
- Clear and concise
- Accurate to the code
- Well-structured with examples

FLOW:
1. Receive reasoning output (analysis of code)
2. Synthesize into user-friendly answer
3. Include relevant code examples
4. Format for readability
"""

from typing import Any

from app.agents.base import BaseAgent, AgentContext, AgentRole


ANSWER_SYSTEM_PROMPT = """You are a helpful code documentation assistant. Your job is
to take technical analysis and produce clear, helpful answers.

Guidelines:
1. Start with a direct answer to the question
2. Explain relevant code with examples when helpful
3. Use clear formatting (headers, bullets, code blocks)
4. Be concise but thorough
5. If uncertain, say so and explain why

Format your response with:
- A brief summary answer (1-2 sentences)
- Detailed explanation with code examples
- Any caveats or limitations
"""


class AnswerGeneratorAgent(BaseAgent):
    """
    Generates final human-readable answers.

    Takes the technical reasoning output and transforms it into
    a clear, well-formatted answer that directly addresses
    the user's original question.
    """

    role = AgentRole.ANSWER_GENERATOR

    def __init__(self, llm_client: Any):
        super().__init__(llm_client)

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Generate final answer from reasoning output.

        Args:
            context: Contains question, reasoning_output, and search_results

        Returns:
            Context updated with final_answer
        """
        context.log("AnswerGenerator: Generating final answer...")

        # Build the prompt
        prompt = self._build_prompt(context)

        # Generate answer
        answer = await self._call_llm(prompt, ANSWER_SYSTEM_PROMPT)

        # Post-process and store
        context.final_answer = self._post_process(answer, context)
        context.log("AnswerGenerator: Answer generated successfully")

        return context

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the answer generation prompt."""
        # Handle case where reasoning failed
        if not context.reasoning_output:
            return f"""
Question: {context.question}
Repository: {context.repo_url}

Unfortunately, the code analysis did not produce results.
Please provide a helpful response explaining that we couldn't find
relevant information and suggest alternative approaches.
"""

        return f"""
Original Question: {context.question}

Repository: {context.repo_url}

Code Analysis:
{context.reasoning_output}

Based on this analysis, provide a clear and helpful answer to the question.
Include relevant code examples from the search results if they help illustrate your answer.
"""

    def _post_process(self, answer: str, context: AgentContext) -> str:
        """
        Post-process the generated answer.

        Adds metadata and handles edge cases.
        """
        # If there were errors, append a note
        if context.errors:
            answer += "\n\n---\n*Note: Some issues occurred during analysis. "
            answer += "The answer may be incomplete.*"

        return answer.strip()
