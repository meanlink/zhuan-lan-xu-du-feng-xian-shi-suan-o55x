import time, json
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate
from src.models import User, Dataset, Job, Report, Delivery, Audit, SupplySpec, Quarantine
from src.services.business import metadata, seed_records, analyze
from src.services import specs as spec_service
from src.services.reports import deliver
from src.utils.security import hash_password
from src.utils.serialization import checksum
import numpy as np

def seed_mixed_records():
    """供稿方直传样例：完成率混用小数与百分数，部分记录观察窗口为7日（应被隔离）。"""
    rng = np.random.default_rng(1009)
    rows = []
    for i in range(56):
        sessions = int(rng.poisson(6))
        completion = float(np.clip(rng.normal(62, 21), 4, 99))
        inactive = int(rng.integers(0, 15))
        issues = int(rng.integers(1, 25))
        logit = -0.5 - 0.20 * sessions - 0.025 * (completion - 50) + 0.27 * inactive - 0.035 * issues
        risk = 1 / (1 + np.exp(-logit))
        row = {"reader_id": f"SP-{i+1:04}", "sessions_14d": sessions, "completion_pct": round(completion, 1),
               "days_inactive": inactive, "issues_read": issues, "renewed": int(rng.random() >= risk)}
        if i < 8:
            row["window_days"] = 7  # 七日窗口混入十四日样本
        elif i < 14:
            row["completion_pct"] = round(completion / 100, 3)  # 小数供稿，未标注单位
        elif i < 20:
            row["completion_pct"] = round(completion / 100, 3)
            row["completion_pct_unit"] = "fraction"  # 小数供稿，供稿方标注单位
        elif i < 24:
            row["window_days"] = 14  # 显式标注且相符
        rows.append(row)
    return rows

def seed():
    migrate()
    with Session() as db:
        for role,name in [('admin','林知 · 业务负责人'),('analyst','陈舟 · 分析员'),('viewer','周禾 · 观察员')]:
            email=role+'@demo.local'
            if not db.scalar(select(User).where(User.email==email)):
                db.add(User(email=email,name=name,role=role,password=hash_password('Demo123!')))
        db.flush()
        admin=db.scalar(select(User).where(User.role=='admin'))
        m=metadata()
        spec=db.scalar(select(SupplySpec).where(SupplySpec.family=='reader-behavior',SupplySpec.status=='active'))
        if not spec:
            spec=SupplySpec(family='reader-behavior',version=1,status='active',fields=spec_service.default_fields(),
                            window_days=14,note='首版供稿口径：完成率以百分数为准，兼容小数供稿换算；观察窗口14日，不符即隔离。',
                            created_by=admin.id,created_at=time.time())
            db.add(spec); db.flush()
        d=db.scalar(select(Dataset).where(Dataset.name==m['dataset_name']))
        if not d:
            rows=seed_records()
            d=Dataset(name=m['dataset_name'],source=m['short']+'-202611.csv',records=rows,checksum=checksum(rows),created_at=time.time(),spec_id=spec.id,lifecycle='current')
            db.add(d); db.flush()
        elif not d.spec_id:
            d.spec_id=spec.id
        demo_name='供稿方直传 · 混排单位样例'
        if not db.scalar(select(Dataset).where(Dataset.name==demo_name)):
            rows=seed_mixed_records()
            accepted,quarantined=spec_service.normalize_batch(rows,spec)
            demo=Dataset(name=demo_name,source='supplier_feed_202611.csv',records=accepted,checksum=checksum(accepted),
                         created_at=time.time(),spec_id=spec.id,lifecycle='current',raw_records=rows)
            db.add(demo); db.flush()
            for q in quarantined:
                db.add(Quarantine(dataset_id=demo.id,row_index=q['row_index'],raw=q['raw'],reasons=q['reasons'],created_at=time.time()))
        if not db.scalar(select(Job).where(Job.name=='基线复核 · '+m['name'])):
            params={p['key']:p['default'] for p in m.get('parameters',[])}
            result=analyze(d.records,params)
            json.dumps(result,ensure_ascii=False,allow_nan=False)
            j=Job(name='基线复核 · '+m['name'],dataset_id=d.id,params=params,status='completed',result=result,created_by=admin.id,created_at=time.time()-3600,finished_at=time.time()-3595,approved=True)
            db.add(j);db.flush()
            r=Report(name='每日业务复核简报',job_id=j.id,destination='业务复核组 · 本地收件箱',interval_seconds=86400,next_run=time.time()+86400,enabled=True)
            db.add(r);db.flush();deliver(db,r)
            db.add(Audit(actor='seed',action='demo.baseline',detail={'dataset':d.id},at=time.time()))
        db.commit()
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in [User,Dataset,Job,Report,Delivery,Audit]}
        print(json.dumps(counts,ensure_ascii=False))
        return counts
if __name__=='__main__':seed()
