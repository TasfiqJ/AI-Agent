"""Pydantic schemas for all LLM outputs.

Every LLM response that drives an action MUST be validated against one of these.
No ast.literal_eval. No regex parsing. Structured output only.
"""

from pydantic import BaseModel, Field


class EndpointInfo(BaseModel):
    method: str = Field(description="HTTP method (GET, POST, PUT, DELETE)")
    path: str = Field(description="URL path")
    handler: str = Field(description="Handler function name")
    file: str = Field(description="Source file path")
    line: int = Field(description="Line number in source file")


class PlanStepSchema(BaseModel):
    id: int = Field(description="Step number")
    description: str = Field(description="What this step does")
    tool_calls: list[str] = Field(description="Tools to be called")
    output_file: str | None = Field(default=None, description="File to create")


class AgentPlanSchema(BaseModel):
    """Structured plan output from the PLAN phase."""

    framework: str = Field(description="Detected framework: flask, fastapi, express")
    endpoints: list[EndpointInfo] = Field(description="Detected API endpoints")
    steps: list[PlanStepSchema] = Field(description="Planned steps")
    test_files: list[str] = Field(description="Test files to generate")
    success_criteria: list[str] = Field(description="How we know we're done")


class ToolCallRequestSchema(BaseModel):
    """LLM requesting a tool call."""

    tool: str = Field(description="Tool name")
    params: dict[str, object] = Field(description="Tool parameters")


class FileDiffSchema(BaseModel):
    """A unified diff to apply to a file."""

    path: str = Field(description="File path")
    diff: str = Field(description="Unified diff content")
    is_new: bool = Field(default=False, description="Whether this is a new file")


class TestFixSchema(BaseModel):
    """A fix to apply after test failure."""

    file: str = Field(description="File to fix")
    diff: str = Field(description="Unified diff to apply")
    reason: str = Field(description="Why this fix is needed")
