from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import SupplySpec
from src.schemas.spec import SpecInput
from src.middlewares.auth import current_user, can_write
from src.services import specs
from src.services.audit import record
from src.utils.serialization import spec_dict
router=APIRouter(prefix='/specs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    return [spec_dict(s) for s in db.scalars(select(SupplySpec).order_by(SupplySpec.family,SupplySpec.version.desc()))]
@router.post('',status_code=201)
def create(data:SpecInput,db=Depends(get_db),u=Depends(can_write)):
    s=specs.create_version(db,data,u); record(db,u.email,'spec.version',{'id':s.id,'family':s.family,'version':s.version})
    db.commit(); return spec_dict(s)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    s=db.get(SupplySpec,id)
    if not s:raise HTTPException(404,'供稿口径不存在')
    return spec_dict(s)
