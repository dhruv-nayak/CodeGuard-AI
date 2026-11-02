from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("user_id", "owner", "name", name="uq_user_repository"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    user = relationship("User", back_populates="repositories")
