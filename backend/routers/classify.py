"""
/classify  — AI comment classification endpoint.
"""
from fastapi import APIRouter

from backend.classifier import classify
from backend.schemas import ClassifyRequest, ClassifyResponse

router = APIRouter(prefix="/classify", tags=["AI Classifier"])


@router.post("/", response_model=ClassifyResponse)
def classify_comment(payload: ClassifyRequest):
    """
    Classify a free-text passenger comment into a category and severity.

    Examples:
      "The bus is always packed after 6 PM." → Crowding / low
      "Driver skipped the university stop."  → Driver Behaviour / medium
      "Felt unsafe, harassment on the bus."  → Safety / high
    """
    result = classify(payload.comment)
    return ClassifyResponse(**result)
