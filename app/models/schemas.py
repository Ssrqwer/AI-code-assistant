"""
app/models/schemas.py
---------------------
Strictly typed Pydantic v2 request and response schemas for every API route.

Design decisions:
  - All string fields use `min_length=1` to reject empty payloads early.
  - `Field(examples=[...])` populates the OpenAPI / Swagger UI automatically.
  - Response models are intentionally kept separate from request models to
    allow them to evolve independently.
"""

from pydantic import BaseModel, Field


# ==============================================================================
# 1. Idea → Code Generation  —  POST /api/v1/generate-code
# ==============================================================================

class GenerateCodeRequest(BaseModel):
    idea: str = Field(
        ...,
        min_length=5,
        description="A natural-language description of the code to generate.",
        examples=["Write a Python function that reverses a linked list."],
    )
    language: str = Field(
        ...,
        min_length=1,
        description="Target programming language (e.g. Python, TypeScript, Go).",
        examples=["Python"],
    )


class GenerateCodeResponse(BaseModel):
    code: str = Field(..., description="The generated raw code (no Markdown fences).")
    language: str = Field(..., description="The target language echoed from the request.")


# ==============================================================================
# 2. Explain Code  —  POST /api/v1/explain-code
# ==============================================================================

class ExplainCodeRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=5,
        description="The source code to be explained.",
    )


class ExplainCodeResponse(BaseModel):
    explanation_md: str = Field(
        ...,
        description="Line-by-line explanation in Markdown format.",
    )


# ==============================================================================
# 3. Time & Space Complexity  —  POST /api/v1/analyze-complexity
# ==============================================================================

class AnalyzeComplexityRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=5,
        description="Code whose algorithmic complexity you want analysed.",
    )


class AnalyzeComplexityResponse(BaseModel):
    time_complexity: str = Field(
        ...,
        description="Big O time complexity (e.g. O(n log n)).",
    )
    space_complexity: str = Field(
        ...,
        description="Big O space complexity (e.g. O(n)).",
    )
    bottlenecks: str = Field(
        ...,
        description="Short description of identified performance bottlenecks.",
    )
    analysis_md: str = Field(
        ...,
        description="Full analysis in Markdown format.",
    )


# ==============================================================================
# 4. Rubber Duck Q&A  —  POST /api/v1/rubber-duck
# ==============================================================================

class RubberDuckRequest(BaseModel):
    code_context: str = Field(
        ...,
        min_length=5,
        description="The code block that provides context for the question.",
    )
    question: str = Field(
        ...,
        min_length=5,
        description="The debugging or conceptual question to ask.",
        examples=["Why does this function always return None?"],
    )


class RubberDuckResponse(BaseModel):
    answer_md: str = Field(
        ...,
        description="Conversational, educational answer in Markdown format.",
    )


# ==============================================================================
# 5. Convert Language  —  POST /api/v1/convert-language
# ==============================================================================

class ConvertLanguageRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=5,
        description="Source code to translate.",
    )
    target_language: str = Field(
        ...,
        min_length=2,
        description="Target programming language (e.g. TypeScript, Rust, Java).",
        examples=["TypeScript"],
    )


class ConvertLanguageResponse(BaseModel):
    converted_code: str = Field(
        ...,
        description="Translated raw code using idiomatic target-language patterns.",
    )
    target_language: str = Field(
        ...,
        description="The target language echoed from the request.",
    )


# ==============================================================================
# 6. Generate Docstring  —  POST /api/v1/generate-docstring
# ==============================================================================

class GenerateDocstringRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=5,
        description="A function or class definition that needs a docstring.",
    )


class GenerateDocstringResponse(BaseModel):
    docstring: str = Field(
        ...,
        description="The standalone docstring string (without surrounding code).",
    )
    code_with_docstring: str = Field(
        ...,
        description="The full original code with the generated docstring inserted.",
    )
