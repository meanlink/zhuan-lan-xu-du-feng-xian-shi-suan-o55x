from sqlalchemy import String, JSON, Double, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class ReversionPlan(Base):
    __tablename__ = 'reversion_plans'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    target_spec_id: Mapped[int] = mapped_column(ForeignKey('supply_specs.id'))
    spec_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # 冻结的目标口径
    status: Mapped[str] = mapped_column(String(20), default='pending')  # pending | running | completed | failed
    epoch: Mapped[int] = mapped_column(Integer, default=0)  # 每次执行递增，旧执行凭过期epoch不得发布
    error: Mapped[str] = mapped_column(String(1000), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)
class ReversionItem(Base):
    __tablename__ = 'reversion_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('reversion_plans.id'))
    source_dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    source_checksum: Mapped[str] = mapped_column(String(64))  # 冻结的原批次指纹
    replacement_dataset_id: Mapped[int | None] = mapped_column(ForeignKey('datasets.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')  # pending | converting | converted | failed
    error: Mapped[str] = mapped_column(String(1000), default='')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
class ReversionLock(Base):
    __tablename__ = 'reversion_locks'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), unique=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('reversion_plans.id'))
