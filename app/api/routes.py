"""
app/api/routes.py
-----------------
API router for all six AI coding assistant endpoints.

Design contract:
  - This file handles HTTP ONLY: request validation, response shaping, logging.
  - All LLM logic is fully delegated to `app.services.gemini_service`.
  - Every route uses its own typed Pydantic request/response pair from schemas.py.
  - Prefix `/api/v1` is applied when this router is mounted in main.py.
"""

import logging

from fastapi import APIRouter

from app.models.schemas import (
    AnalyzeComplexityRequest,
    AnalyzeComplexityResponse,
    ConvertLanguageRequest,
    ConvertLanguageResponse,
    ExplainCodeRequest,
    ExplainCodeResponse,
    GenerateCodeRequest,
    GenerateCodeResponse,
    GenerateDocstringRequest,
    GenerateDocstringResponse,
    RubberDuckRequest,
    RubberDuckResponse,
)
from app.services import gemini_service as svc

logger = logging.getLogger(__name__)

router = APIRouter()


# ==============================================================================
# 1. Idea → Code Generation
# ==============================================================================

@router.post(
    "/generate-code",
    response_model=GenerateCodeResponse,
    summary="Convert a natural-language idea into working code",
    tags=["Code Generation"],
)
async def generate_code(request: GenerateCodeRequest) -> GenerateCodeResponse:
    """
    Provide a plain-English *idea* and a *language*.
    Gemini returns **raw, fence-free code** in the requested language.
    """
    logger.info(
        "generate_code | language=%r | idea_preview=%.80s",
        request.language,
        request.idea,
    )
    result = svc.generate_code(idea=request.idea, language=request.language)
    return GenerateCodeResponse(**result)


# ==============================================================================
# 2. Explain Code
# ==============================================================================

@router.post(
    "/explain-code",
    response_model=ExplainCodeResponse,
    summary="Get a line-by-line Markdown explanation of code",
    tags=["Code Understanding"],
)
async def explain_code(request: ExplainCodeRequest) -> ExplainCodeResponse:
    """
    Submit any code snippet.
    Gemini returns a clean Markdown explanation, broken down line-by-line.
    """
    logger.info("explain_code | code_length=%d", len(request.code))
    result = svc.explain_code(code=request.code)
    return ExplainCodeResponse(**result)


# ==============================================================================
# 3. Analyze Complexity
# ==============================================================================

@router.post(
    "/analyze-complexity",
    response_model=AnalyzeComplexityResponse,
    summary="Get Big O time/space complexity and bottleneck analysis",
    tags=["Code Analysis"],
)
async def analyze_complexity(request: AnalyzeComplexityRequest) -> AnalyzeComplexityResponse:
    """
    Gemini analyses the code and returns a **structured JSON** payload with:
    - `time_complexity` — Big O time notation  
    - `space_complexity` — Big O space notation  
    - `bottlenecks` — Short plain-text bottleneck description  
    - `analysis_md` — Full Markdown analysis  

    The Gemini SDK is called with `response_mime_type="application/json"`
    to guarantee a parsable response.
    """
    logger.info("analyze_complexity | code_length=%d", len(request.code))
    result = svc.analyze_complexity(code=request.code)
    return AnalyzeComplexityResponse(**result)


# ==============================================================================
# 4. Rubber Duck Q&A
# ==============================================================================

@router.post(
    "/rubber-duck",
    response_model=RubberDuckResponse,
    summary="Ask a debugging question in the context of your code",
    tags=["Debugging"],
)
async def rubber_duck(request: RubberDuckRequest) -> RubberDuckResponse:
    """
    Provide a *code_context* block and a *question*.  
    Gemini acts as a friendly rubber-duck partner and returns a
    conversational, educational **Markdown answer**.
    """
    logger.info(
        "rubber_duck | question_preview=%.80s | context_length=%d",
        request.question,
        len(request.code_context),
    )
    result = svc.rubber_duck(
        code_context=request.code_context,
        question=request.question,
    )
    return RubberDuckResponse(**result)


# ==============================================================================
# 5. Convert Language
# ==============================================================================

@router.post(
    "/convert-language",
    response_model=ConvertLanguageResponse,
    summary="Translate code from one programming language to another",
    tags=["Code Translation"],
)
async def convert_language(request: ConvertLanguageRequest) -> ConvertLanguageResponse:
    """
    Provide source code and a *target_language*.  
    Gemini translates the code using idiomatic patterns of the target language
    and returns **raw, fence-free translated code**.
    """
    logger.info(
        "convert_language | target=%r | code_length=%d",
        request.target_language,
        len(request.code),
    )
    result = svc.convert_language(
        code=request.code,
        target_language=request.target_language,
    )
    return ConvertLanguageResponse(**result)


# ==============================================================================
# 6. Generate Docstring
# ==============================================================================

@router.post(
    "/generate-docstring",
    response_model=GenerateDocstringResponse,
    summary="Auto-generate a professional docstring for a function or class",
    tags=["Documentation"],
)
async def generate_docstring(request: GenerateDocstringRequest) -> GenerateDocstringResponse:
    """
    Submit a function or class definition.  
    Returns:
    - `docstring` — The standalone docstring text  
    - `code_with_docstring` — The full code with the docstring injected  
    """
    logger.info("generate_docstring | code_length=%d", len(request.code))
    result = svc.generate_docstring(code=request.code)
    return GenerateDocstringResponse(**result)
