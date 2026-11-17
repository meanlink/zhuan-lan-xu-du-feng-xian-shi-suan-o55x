from sqlalchemy import String, JSON, Double, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Quarantine(Base):
    __tablename__ = 'quarantines'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    row_index: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[float] = mapped_column(Double)
