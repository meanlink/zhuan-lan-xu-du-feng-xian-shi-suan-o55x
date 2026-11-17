"""换版案：冻结原批次与目标口径版本，逐批生成替代批次，全部校验成功才一次性切换新试验入口。

并发：同一原批次由 reversion_locks 唯一约束保护，后到案 409 拒绝。
恢复：每个替代批次在单独事务内落库并推进条目状态，中断后按条目进度续跑。
幂等：已 converted 的条目跳过；重试不新增替代批次。
防旧发布：发布以 (id, status, epoch) 条件更新为闸，旧执行晚到时更新不到行，不得发布。
"""
import time
from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from redis import Redis
from src.config.database import Session as SessionLocal
from src.config.settings import REDIS_URL
from src.models import Dataset, Quarantine, SupplySpec, ReversionPlan, ReversionItem, ReversionLock
from src.services import specs
from src.services.business import validate_records
from src.services.audit import record
from src.utils.serialization import checksum


def create(db, data, user):
    target = db.get(SupplySpec, data.target_spec_id)
    if not target:
        raise HTTPException(404, '目标口径版本不存在')
    if target.status != 'active':
        raise HTTPException(409, '只能换到现行口径版本')
    sources = []
    for dataset_id in dict.fromkeys(data.source_dataset_ids):
        d = db.get(Dataset, dataset_id)
        if not d:
            raise HTTPException(404, f'原批次 {dataset_id} 不存在')
        if d.lifecycle != 'current':
            raise HTTPException(409, f'批次「{d.name}」不是现行批次，不能作为换版原批次')
        if d.spec_id == target.id:
            raise HTTPException(422, f'批次「{d.name}」已是目标口径版本，无需换版')
        if d.spec_id:
            source_spec = db.get(SupplySpec, d.spec_id)
            if source_spec and source_spec.family != target.family:
                raise HTTPException(422, f'批次「{d.name}」属于另一口径族，不能跨族换版')
        sources.append(d)
    if not sources:
        raise HTTPException(422, '至少选择一个原批次')
    plan = ReversionPlan(name=data.name.strip(), target_spec_id=target.id, spec_snapshot=specs.snapshot(target),
                         status='pending', epoch=0, created_by=user.id, created_at=time.time())
    db.add(plan)
    db.flush()
    for d in sources:
        db.add(ReversionItem(plan_id=plan.id, source_dataset_id=d.id, source_checksum=d.checksum))
        db.add(ReversionLock(source_dataset_id=d.id, plan_id=plan.id))
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, '其中已有原批次被其他进行中的换版案锁定，后到案不予受理')
    return plan


def enqueue(plan_id):
    try:
        r = Redis.from_url(REDIS_URL)
        r.rpush('reversion:queue', plan_id)
        r.close()
    except Exception:
        pass  # SQL pending 状态是持久兜底，worker tick 会拾取


def retry(db, plan, user):
    if plan.status != 'failed':
        raise HTTPException(409, '仅失败的换版案可以重试；处理中的案由 worker 按进度恢复')
    for item in db.scalars(select(ReversionItem).where(ReversionItem.plan_id == plan.id)):
        if item.status in ('pending', 'converting', 'failed'):
            item.status = 'pending'
            item.error = ''
    plan.status = 'pending'
    plan.error = ''
    plan.finished_at = None
    db.flush()
    record(db, user.email, 'reversion.retry', {'id': plan.id})


def _fail_plan(db, plan, message):
    plan.status = 'failed'
    plan.error = message[:990]
    plan.finished_at = time.time()
    db.execute(delete(ReversionLock).where(ReversionLock.plan_id == plan.id))
    record(db, 'worker', 'reversion.failed', {'id': plan.id, 'error': plan.error})
    db.commit()


def _process_item(db, plan, item):
    """在单个事务内生成一个替代批次并推进条目状态；失败抛 HTTPException 由调用方落失败态。"""
    item.attempts += 1
    if item.replacement_dataset_id:
        item.status = 'converted'  # 重试不新增替代批次
        return
    source = db.get(Dataset, item.source_dataset_id)
    if not source:
        raise HTTPException(409, f'原批次 {item.source_dataset_id} 已不存在')
    if source.checksum != item.source_checksum:
        raise HTTPException(409, f'原批次「{source.name}」指纹与立案时冻结值不符')
    rows = source.raw_records if source.raw_records else source.records
    accepted, quarantined = specs.normalize_batch(rows, plan.spec_snapshot)
    invalid = validate_records(accepted)
    if invalid:
        raise HTTPException(422, f'原批次「{source.name}」按新口径换算后未通过校验：{invalid}')
    version = plan.spec_snapshot['version']
    name = f'{source.name} · 口径v{version}'
    if db.scalar(select(Dataset).where(Dataset.name == name)):
        name = f'{name} · 案{plan.id}'
    replacement = Dataset(name=name, source=source.source, records=accepted, checksum=checksum(accepted),
                          created_at=time.time(), spec_id=plan.target_spec_id, lifecycle='staging',
                          parent_id=source.id, raw_records=source.raw_records)
    db.add(replacement)
    db.flush()
    for q in quarantined:
        db.add(Quarantine(dataset_id=replacement.id, row_index=q['row_index'], raw=q['raw'],
                          reasons=q['reasons'], created_at=time.time()))
    item.replacement_dataset_id = replacement.id
    item.status = 'converted'


def execute(plan_id):
    with SessionLocal() as db:
        claimed = db.execute(update(ReversionPlan).where(ReversionPlan.id == plan_id,
                                                         ReversionPlan.status.in_(['pending', 'running']))
                             .values(status='running', epoch=ReversionPlan.epoch + 1)
                             .execution_options(synchronize_session=False)).rowcount
        if claimed != 1:
            db.rollback()
            return
        # 上次中断可能留下 converting 状态的条目；其替代批次与条目更新同属一个事务，重置安全
        db.execute(update(ReversionItem).where(ReversionItem.plan_id == plan_id, ReversionItem.status == 'converting')
                   .values(status='pending'))
        db.commit()
        epoch = db.scalar(select(ReversionPlan.epoch).where(ReversionPlan.id == plan_id))
    while True:
        with SessionLocal() as db:
            plan = db.get(ReversionPlan, plan_id)
            if not plan or plan.status != 'running' or plan.epoch != epoch:
                return  # 已有更新的执行接管，本执行不得继续
            item = db.scalar(select(ReversionItem).where(ReversionItem.plan_id == plan.id,
                                                         ReversionItem.status == 'pending').order_by(ReversionItem.id).limit(1))
            if item is None:
                break
            claimed = db.execute(update(ReversionItem).where(ReversionItem.id == item.id, ReversionItem.status == 'pending')
                                 .values(status='converting')).rowcount
            if claimed != 1:
                continue
            try:
                _process_item(db, plan, db.get(ReversionItem, item.id))
            except HTTPException as exc:
                db.rollback()
                plan = db.get(ReversionPlan, plan_id)
                failed_item = db.get(ReversionItem, item.id)
                failed_item.status = 'failed'
                failed_item.error = str(exc.detail)[:990]
                failed_item.attempts += 1
                db.flush()
                _fail_plan(db, plan, f'批次 {item.source_dataset_id} 换版失败：{exc.detail}。已保留旧版入口。')
                return
            except Exception as exc:
                db.rollback()
                plan = db.get(ReversionPlan, plan_id)
                failed_item = db.get(ReversionItem, item.id)
                failed_item.status = 'failed'
                failed_item.error = str(exc)[:990]
                failed_item.attempts += 1
                db.flush()
                _fail_plan(db, plan, f'批次 {item.source_dataset_id} 换版异常：{exc}。已保留旧版入口。')
                return
            db.commit()
    # 全部校验成功：一次性切换新试验入口。条件更新是发布闸，旧执行晚回时更新不到行。
    with SessionLocal() as db:
        switched = db.execute(update(ReversionPlan).where(ReversionPlan.id == plan_id,
                                                          ReversionPlan.status == 'running',
                                                          ReversionPlan.epoch == epoch)
                              .values(status='completed', finished_at=time.time())
                              .execution_options(synchronize_session=False)).rowcount
        if switched != 1:
            db.rollback()
            return
        for item in db.scalars(select(ReversionItem).where(ReversionItem.plan_id == plan_id)):
            source = db.get(Dataset, item.source_dataset_id)
            replacement = db.get(Dataset, item.replacement_dataset_id)
            if source:
                source.lifecycle = 'superseded'
            if replacement:
                replacement.lifecycle = 'current'
        db.execute(delete(ReversionLock).where(ReversionLock.plan_id == plan_id))
        record(db, 'worker', 'reversion.completed', {'id': plan_id})
        db.commit()
