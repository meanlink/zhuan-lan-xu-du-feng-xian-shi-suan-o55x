import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d, spec=None, quarantined=0):
    out={'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at,
         'lifecycle':d.lifecycle or 'current', 'spec_id':d.spec_id, 'parent_id':d.parent_id, 'quarantined':quarantined}
    if spec: out['spec']={'id':spec.id, 'family':spec.family, 'version':spec.version, 'window_days':spec.window_days}
    return out
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def spec_dict(s):
    return {k:getattr(s,k) for k in ['id','family','version','status','fields','window_days','note','created_at']}
def quarantine_dict(q):
    return {k:getattr(q,k) for k in ['id','dataset_id','row_index','raw','reasons','created_at']}
def item_dict(i, names=None):
    out={'id':i.id, 'source_dataset_id':i.source_dataset_id, 'replacement_dataset_id':i.replacement_dataset_id,
         'status':i.status, 'error':i.error, 'attempts':i.attempts}
    if names:
        out['source_name']=names.get(i.source_dataset_id,'')
        out['replacement_name']=names.get(i.replacement_dataset_id,'') if i.replacement_dataset_id else ''
    return out
def plan_dict(p, items=None, names=None):
    out={'id':p.id, 'name':p.name, 'target_spec_id':p.target_spec_id, 'status':p.status, 'error':p.error,
         'created_at':p.created_at, 'finished_at':p.finished_at,
         'spec_version':(p.spec_snapshot or {}).get('version'), 'window_days':(p.spec_snapshot or {}).get('window_days')}
    if items is not None:
        out['items']=[item_dict(i,names) for i in items]
        out['progress']={'total':len(items), 'converted':sum(1 for i in items if i.status=='converted')}
    return out
