from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.user import User


def save_review(
    db: Session,
    user: User,
    review_id: str,
    result: dict,
    review_type: str = "code",
    filename: str = "",
    repository: str = "",
) -> Review:
    row = Review(
        review_id=review_id,
        user_id=user.id,
        review_type=review_type,
        filename=filename,
        repository=repository,
        score=result.get("score"),
        summary=result.get("summary")
        or result.get("ai_summary")
        or "GitHub pull request review completed.",
        result_json=result,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_reviews(db: Session, user: User, limit: int = 50) -> list[Review]:
    query = (
        select(Review)
        .where(Review.user_id == user.id)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def get_review(db: Session, user: User, review_id: str) -> Review | None:
    query = select(Review).where(Review.review_id == review_id, Review.user_id == user.id)
    return db.scalar(query)
