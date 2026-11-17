from sqlalchemy import String, JSON, Double, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    source: Mapped[str] = mapped_column(String(200), default='manual.json')
    records: Mapped[list] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Double)
    spec_id: Mapped[int | None] = mapped_column(ForeignKey('supply_specs.id'), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), default='current')  # staging | current | superseded
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('datasets.id'), nullable=True)
    raw_records: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 供稿原值，换版时据此重新换算
