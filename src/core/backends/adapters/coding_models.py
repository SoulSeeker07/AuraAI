from pydantic import BaseModel, Field


class RequirementModel(BaseModel):
    """
    Distinguishes between user-explicit requirements and LLM-inferred requirements.
    """
    project_name: str = Field(description="The name of the project or feature")
    language: str = Field(description="The programming language to use")
    explicit_requirements: list[str] = Field(
        description="Requirements explicitly stated by the user"
    )
    inferred_requirements: list[str] = Field(
        description="Reasonable defaults or architectural decisions inferred by the model"
    )


class GeneratedFile(BaseModel):
    path: str = Field(description="The relative path to the file within the repository")
    content: str = Field(description="The source code content for the file")


class CodeGenerationPlan(BaseModel):
    """
    A structured plan containing files to be written to the workspace.
    """
    files: list[GeneratedFile] = Field(
        description="List of files to generate and their contents"
    )
