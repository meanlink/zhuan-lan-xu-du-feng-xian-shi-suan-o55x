import time
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Dataset, Quarantine, SupplySpec
from src.services import specs
from src.utils.serialization import checksum
def create(db, data):
    name=data.name.strip()
    if len(name)<2: raise HTTPException(422, '批次名称去除空格后至少需要两个字符')
    if db.scalar(select(Dataset).where(Dataset.name==name)):
        raise HTTPException(409, '该数据批次名已存在，请修改名称')
    if data.spec_id:
        spec=db.get(SupplySpec,data.spec_id)
        if not spec: raise HTTPException(404,'供稿口径不存在')
    else:
        spec=specs.active_spec(db)
        if not spec: raise HTTPException(409,'尚无现行供稿口径，请先在口径页建立版本')
    accepted,quarantined=specs.normalize_batch(data.records,spec)
    if not accepted: raise HTTPException(422,'全部记录均被隔离，没有可接入的合格样本')
    d=Dataset(name=name, source=data.source, records=accepted, checksum=checksum(accepted), created_at=time.time(),
              spec_id=spec.id, lifecycle='current', raw_records=data.records)
    db.add(d); db.flush()
    for q in quarantined:
        db.add(Quarantine(dataset_id=d.id, row_index=q['row_index'], raw=q['raw'], reasons=q['reasons'], created_at=time.time()))
    db.flush()
    return d
