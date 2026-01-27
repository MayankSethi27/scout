"""
Base classes for the agent architecture.

All agents and tools inherit from these base classes to ensure
consistent interfaces and behavior across the system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class AgentRole(Enum):
    """Defines the role of each agent in the system."""
    PLANNER = "planner"
    REASONING = "reasoning"
    ANSWER_GENERATOR = "answer_generator"


class ToolType(Enum):
    """Types of tools available to agents."""
    CODE_LOADER = "code_loader"
    CODE_INDEXER = "code_indexer"
    SEARCH = "search"


@dataclass
class AgentContext:
    """
    Shared context passed between agents during execution.

    This context accumulates data as it flows through the pipeline:
    User Question -> Planner -> Tools -> Reasoning -> Answer
    """
    # Input
    question: str
    repo_url: str

    # State tracking
    repo_path: Optional[str] = None
    is_indexed: bool = False

    # Accumulated results
    plan: Optional[dict] = None
    search_results: list = field(default_factory=list)
    reasoning_output: Optional[str] = None
    final_answer: Optional[str] = None

    # Metadata
    errors: list = field(default_factory=list)
    execution_log: list = field(default_factory=list)

    def log(self, message: str) -> None:
        """Add entry to execution log."""
        self.execution_log.append(message)

    def add_error(self, error: str) -> None:
        """Record an error that occurred during execution."""
        self.errors.append(error)


@dataclass
class ToolResult:
    """Result returned by a tool after execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None


class BaseTool(ABC):
    """
    Base class for all tools.

    Tools are stateless components that perform specific actions:
    - CodeLoaderTool: Clone/load repositories
    - CodeIndexerTool: Index code into vector store
    - SearchTool: Search for relevant code
    """

    name: str = "base_tool"
    description: str = "Base tool description"

    @abstractmethod
    async def execute(self, context: AgentContext, **kwargs) -> ToolResult:
        """
        Execute the tool's action.

        Args:
            context: Shared agent context
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success status and data/error
        """
        pass


class BaseAgent(ABC):
    """
    Base class for all agents.

    Agents are LLM-powered components that make decisions:
    - PlannerAgent: Decides what tools to use and in what order
    - ReasoningAgent: Analyzes search results and extracts insights
    - AnswerGeneratorAgent: Produces the final human-readable answer
    """

    role: AgentRole

    def __init__(self, llm_client: Any):
        """
        Initialize agent with LLM client.

        Args:
            llm_client: Client for making LLM API calls
        """
        self.llm = llm_client

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Execute the agent's logic.

        Args:
            context: Shared agent context with accumulated data

        Returns:
            Updated context with agent's output
        """
        pass

    async def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Make a call to the LLM.

        Args:
            prompt: User prompt to send
            system_prompt: Optional system prompt

        Returns:
            LLM response text
        """
        return await self.llm.generate(prompt, system_prompt)
