from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from src.config.database import get_db
from src.models import Dataset, Quarantine, SupplySpec
from src.schemas.dataset import DatasetInput
from src.middlewares.auth import current_user, can_write
from src.services import datasets
from src.services.audit import record
from src.utils.serialization import dataset_dict, quarantine_dict
router=APIRouter(prefix='/datasets')
def _maps(db):
    specs={s.id:s for s in db.scalars(select(SupplySpec))}
    counts=dict(db.execute(select(Quarantine.dataset_id,func.count()).group_by(Quarantine.dataset_id)).all())
    return specs,counts
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    specs,counts=_maps(db)
    return [dataset_dict(d,specs.get(d.spec_id),counts.get(d.id,0)) for d in db.scalars(select(Dataset).order_by(Dataset.id.desc()))]
@router.post('',status_code=201)
def create(data:DatasetInput,db=Depends(get_db),u=Depends(can_write)):
    d=datasets.create(db,data); record(db,u.email,'dataset.create',{'id':d.id,'rows':len(d.records),'spec_id':d.spec_id})
    db.commit()
    quarantined=db.scalar(select(func.count()).select_from(Quarantine).where(Quarantine.dataset_id==d.id))
    return dataset_dict(d,quarantined=quarantined)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    d=db.get(Dataset,id)
    if not d:raise HTTPException(404,'数据批次不存在')
    specs,counts=_maps(db)
    return {**dataset_dict(d,specs.get(d.spec_id),counts.get(d.id,0)),'records':d.records}
@router.get('/{id}/quarantines')
def quarantines(id:int,db=Depends(get_db),u=Depends(current_user)):
    if not db.get(Dataset,id):raise HTTPException(404,'数据批次不存在')
    return [quarantine_dict(q) for q in db.scalars(select(Quarantine).where(Quarantine.dataset_id==id).order_by(Quarantine.row_index))]
