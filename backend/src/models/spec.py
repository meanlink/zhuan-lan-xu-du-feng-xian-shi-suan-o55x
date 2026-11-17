from sqlalchemy import String, JSON, Double, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class SupplySpec(Base):
    __tablename__ = 'supply_specs'
    __table_args__ = (UniqueConstraint('family', 'version', name='uq_spec_family_version'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    family: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='active')  # active | superseded
    fields: Mapped[list] = mapped_column(JSON, default=list)
    window_days: Mapped[int] = mapped_column(Integer, default=14)
    note: Mapped[str] = mapped_column(String(500), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
