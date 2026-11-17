"""供稿口径：字段、单位与观察窗口的版本化声明；接入时保留原值并按口径换算，窗口不符隔离。"""
import math
import time
from fastapi import HTTPException
from sqlalchemy import select
from src.models import SupplySpec
from src.services.business import FEATURES

REQUIRED_KEYS = ["reader_id"] + FEATURES + ["renewed"]


def default_fields():
    """模型契约要求的字段集合；口径只能调整标签、单位接受范围、取值边界与观察窗口。"""
    return [
        {"key": "reader_id", "label": "匿名读者", "type": "string"},
        {"key": "sessions_14d", "label": "14日访问次数", "type": "number", "min": 0},
        {"key": "completion_pct", "label": "阅读完成率", "type": "number", "unit": "percent", "accept_units": ["fraction"], "min": 0, "max": 100},
        {"key": "days_inactive", "label": "连续未读天数", "type": "number", "min": 0},
        {"key": "issues_read", "label": "已读期数", "type": "number", "min": 0},
        {"key": "renewed", "label": "实际续读(1/0)", "type": "number", "labels": [0, 1]},
    ]


def validate_spec(fields, window_days):
    if not isinstance(window_days, int) or isinstance(window_days, bool) or not 1 <= window_days <= 60:
        raise HTTPException(422, '观察窗口须为 1~60 的整数天数')
    if not isinstance(fields, list) or not fields:
        raise HTTPException(422, '口径至少需要声明一个字段')
    by_key = {}
    for f in fields:
        if not isinstance(f, dict) or not f.get('key'):
            raise HTTPException(422, '每个字段声明都需要 key')
        by_key[f['key']] = f
    if set(by_key) != set(REQUIRED_KEYS) or len(by_key) != len(fields):
        raise HTTPException(422, '口径字段须恰好覆盖：' + '、'.join(REQUIRED_KEYS))
    for f in fields:
        key = f['key']
        if not str(f.get('label', '')).strip():
            raise HTTPException(422, f'字段 {key} 需要中文标签')
        if key == 'reader_id':
            if f.get('type') != 'string':
                raise HTTPException(422, 'reader_id 必须为字符串类型')
            continue
        if f.get('type') != 'number':
            raise HTTPException(422, f'字段 {key} 必须为数值类型')
        for bound in ('min', 'max'):
            if bound in f and (not isinstance(f[bound], (int, float)) or isinstance(f[bound], bool) or not math.isfinite(float(f[bound]))):
                raise HTTPException(422, f'字段 {key} 的 {bound} 必须为有限数值')
        if 'min' in f and 'max' in f and float(f['min']) >= float(f['max']):
            raise HTTPException(422, f'字段 {key} 的取值下限必须小于上限')
        if key == 'completion_pct':
            if f.get('unit') != 'percent' or float(f.get('min', 0)) != 0 or float(f.get('max', 100)) != 100:
                raise HTTPException(422, '完成率的标准单位固定为百分数(0~100)，供稿小数仅作为可接受单位换算接入')
            if set(f.get('accept_units', [])) - {'fraction'}:
                raise HTTPException(422, '完成率仅支持额外接受小数(fraction)单位')
        if key == 'renewed' and [int(v) for v in f.get('labels', [])] != [0, 1]:
            raise HTTPException(422, '续读标签只能声明为 0/1')
    return fields


def create_version(db, data, user):
    family = data.family.strip()
    if len(family) < 2:
        raise HTTPException(422, '口径族名称去除空格后至少需要两个字符')
    validate_spec(data.fields, data.window_days)
    latest = db.scalar(select(SupplySpec).where(SupplySpec.family == family).order_by(SupplySpec.version.desc()).limit(1))
    version = (latest.version + 1) if latest else 1
    if latest and latest.status == 'active':
        latest.status = 'superseded'
    spec = SupplySpec(family=family, version=version, status='active', fields=data.fields,
                      window_days=data.window_days, note=data.note.strip(), created_by=user.id, created_at=time.time())
    db.add(spec)
    db.flush()
    return spec


def active_spec(db, family=None):
    q = select(SupplySpec).where(SupplySpec.status == 'active')
    if family:
        q = q.where(SupplySpec.family == family)
    return db.scalar(q.order_by(SupplySpec.family, SupplySpec.version.desc()).limit(1))


def snapshot(spec):
    return {'id': spec.id, 'family': spec.family, 'version': spec.version,
            'fields': spec.fields, 'window_days': spec.window_days}


def normalize_row(row, spec, index):
    """按口径换算一行。窗口不符返回隔离原因；结构问题抛 422；成功返回带换算依据的记录。"""
    fields = spec['fields'] if isinstance(spec, dict) else spec.fields
    window_days = spec['window_days'] if isinstance(spec, dict) else spec.window_days
    hinted = row.get('window_days')
    if hinted is not None and hinted != '':
        try:
            hinted_value = float(hinted)
        except (TypeError, ValueError):
            hinted_value = None
        if hinted_value is None or hinted_value != float(window_days):
            shown = hinted if hinted_value is None else int(hinted_value)
            return None, [f'观察窗口为{shown}日，与口径要求的{window_days}日不符']
    record, provenance = {}, {}
    for f in fields:
        key, label = f['key'], f['label']
        value = row.get(key)
        if value is None or value == '':
            raise HTTPException(422, f'第 {index+1} 行缺少字段 {label}')
        if f['type'] == 'string':
            record[key] = str(value)
            continue
        try:
            if isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError()
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            raise HTTPException(422, f'第 {index+1} 行 {label} 必须为有限数值')
        unit_hint = row.get(f'{key}_unit')
        if unit_hint not in (None, ''):
            if unit_hint not in ('percent', 'fraction'):
                raise HTTPException(422, f'第 {index+1} 行 {label} 的单位标注无效')
            if unit_hint == 'fraction':
                if 'fraction' not in f.get('accept_units', []):
                    raise HTTPException(422, f'第 {index+1} 行 {label} 标注为小数，但当前口径不接受小数单位')
                provenance[key] = {'raw': number, 'raw_unit': 'fraction', 'conversion': '×100',
                                   'value': number * 100, 'basis': '供稿标注为小数，按口径换算为百分数'}
                number = number * 100
        elif f.get('unit') == 'percent' and 'fraction' in f.get('accept_units', []) and 0 <= number <= 1:
            provenance[key] = {'raw': number, 'raw_unit': 'fraction', 'conversion': '×100',
                               'value': number * 100, 'basis': '原值不大于1，按小数供稿换算为百分数'}
            number = number * 100
        if 'labels' in f and (number != int(number) or int(number) not in [int(v) for v in f['labels']]):
            raise HTTPException(422, f'第 {index+1} 行 {label} 只能为 0/1')
        if 'min' in f and number < float(f['min']) or 'max' in f and number > float(f['max']):
            raise HTTPException(422, f'第 {index+1} 行 {label} 超出口径范围 {f.get("min", "-∞")}~{f.get("max", "+∞")}')
        record[key] = number
    if provenance:
        record['_provenance'] = provenance
    return record, []


def normalize_batch(rows, spec):
    """整批换算：返回 (合格记录, 隔离记录)。隔离记录含行号、原值与原因。"""
    accepted, quarantined = [], []
    for index, row in enumerate(rows):
        record, reasons = normalize_row(row, spec, index)
        if reasons:
            quarantined.append({'row_index': index, 'raw': row, 'reasons': reasons})
        else:
            accepted.append(record)
    return accepted, quarantined
