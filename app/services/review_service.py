from uuid import uuid4
from app.schemas.review import ReviewRequest, ReviewResponse, AIReview
from app.services.analyzer import analyze_source
from app.services.test_suggester import suggest_tests
from app.services.ai_providers import get_hybrid_review

def calculate_score(findings) -> int:
    deductions = {"critical": 25, "high": 15, "medium": 8, "low": 3, "info": 1}
    return max(0, 100 - sum(deductions[f.severity] for f in findings))

async def review_code(payload: ReviewRequest) -> ReviewResponse:
    code = payload.code.strip()
    if not code:
        raise ValueError("Code cannot be empty.")

    findings = analyze_source(code, payload.language)
    suggestions = (suggest_tests(code) if payload.language == "python" else [
        "test_valid_input_and_expected_output",
        "test_invalid_or_malformed_input_is_rejected",
        "test_boundary_conditions_and_empty_values",
        "test_untrusted_input_is_handled_safely",
    ])
    ai_data, provider_used, provider_errors = await get_hybrid_review(
        payload.filename, code, payload.ai_provider, payload.language
    )

    ai_review = None
    if ai_data:
        try:
            ai_review = AIReview.model_validate(ai_data)
        except Exception:
            provider_errors.append("AI response could not be validated against the expected review schema.")
            ai_data = None

    limitations = [
        "Submitted source code is parsed and inspected; it is not executed.",
        "Static analysis uses selected language-specific heuristics; it is not a full compiler or SAST engine and cannot prove that software is secure or bug-free.",
        "Non-Python language checks use regular-expression patterns and may produce false positives or miss context-dependent issues.",
        "AI findings, suggested fixes and generated tests are advisory and require developer review.",
        "Generated test code is returned as text and is not executed by this service.",
    ]
    if not ai_data:
        limitations.append("No AI provider returned a valid review. Static analysis remains available.")
    if provider_errors:
        limitations.append("Provider attempts: " + " | ".join(provider_errors))

    summary = (
        f"Static analysis completed. {len(findings)} finding(s) identified."
        if not ai_review else ai_review.summary
    )

    return ReviewResponse(
        review_id=str(uuid4()),
        filename=payload.filename,
        language=payload.language,
        status="completed",
        score=calculate_score(findings),
        summary=summary,
        findings=findings,
        suggested_tests=suggestions,
        ai_reviewed=bool(ai_review),
        ai_provider=provider_used,
        ai_review=ai_review,
        limitations=limitations,
    )
