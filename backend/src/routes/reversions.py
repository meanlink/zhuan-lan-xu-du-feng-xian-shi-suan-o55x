from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Dataset, ReversionPlan, ReversionItem
from src.schemas.reversion import ReversionInput
from src.middlewares.auth import current_user, can_write
from src.services import reversions
from src.services.audit import record
from src.utils.serialization import plan_dict
router=APIRouter(prefix='/reversions')
def _names(db,items):
    ids={i.source_dataset_id for i in items}|{i.replacement_dataset_id for i in items if i.replacement_dataset_id}
    return {d.id:d.name for d in db.scalars(select(Dataset).where(Dataset.id.in_(ids)))} if ids else {}
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    out=[]
    for p in db.scalars(select(ReversionPlan).order_by(ReversionPlan.id.desc()).limit(50)):
        items=list(db.scalars(select(ReversionItem).where(ReversionItem.plan_id==p.id).order_by(ReversionItem.id)))
        out.append(plan_dict(p,items,_names(db,items)))
    return out
@router.post('',status_code=201)
def create(data:ReversionInput,db=Depends(get_db),u=Depends(can_write)):
    p=reversions.create(db,data,u); record(db,u.email,'reversion.create',{'id':p.id,'target_spec':p.target_spec_id,'sources':data.source_dataset_ids})
    db.commit(); reversions.enqueue(p.id)
    items=list(db.scalars(select(ReversionItem).where(ReversionItem.plan_id==p.id).order_by(ReversionItem.id)))
    return plan_dict(p,items,_names(db,items))
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    p=db.get(ReversionPlan,id)
    if not p: raise HTTPException(404,'换版案不存在')
    items=list(db.scalars(select(ReversionItem).where(ReversionItem.plan_id==p.id).order_by(ReversionItem.id)))
    return plan_dict(p,items,_names(db,items))
@router.post('/{id}/retry')
def retry(id:int,db=Depends(get_db),u=Depends(can_write)):
    p=db.get(ReversionPlan,id)
    if not p: raise HTTPException(404,'换版案不存在')
    reversions.retry(db,p,u); db.commit(); reversions.enqueue(p.id)
    items=list(db.scalars(select(ReversionItem).where(ReversionItem.plan_id==p.id).order_by(ReversionItem.id)))
    return plan_dict(p,items,_names(db,items))
