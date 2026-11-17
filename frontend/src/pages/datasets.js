import {datasets,specs} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {Lifecycle} from '../constants/enums.js';
import {esc,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {parseCSV} from '../utils/csv.js';
const quarView=qs=>qs.length?table([{key:'row',label:'原行号'},{key:'reasons',label:'隔离原因'},{key:'raw',label:'供稿原值'}],qs.map(q=>({row:q.row_index+1,reasons:q.reasons.join('；'),raw:JSON.stringify(q.raw)})),'本批没有隔离记录。'):'<div class="empty">本批没有隔离记录。</div>';
const provView=records=>{
 const rows=records.flatMap(r=>Object.entries(r._provenance||{}).map(([k,p])=>({reader:r.reader_id,field:k,raw:p.raw+'（'+(p.raw_unit==='fraction'?'小数':p.raw_unit)+'）',conv:p.conversion,value:p.value,basis:p.basis})));
 return rows.length?table([{key:'reader',label:'匿名读者'},{key:'field',label:'字段'},{key:'raw',label:'供稿原值'},{key:'conv',label:'换算'},{key:'value',label:'口径值'},{key:'basis',label:'转换依据'}],rows):'<div class="empty">本批记录均与口径单位一致，无需换算。</div>';
};
export async function dataPage(){
 workspace.datasets=await datasets.list();const activeSpec=(await specs.list()).find(s=>s.status==='active');
 let selected=workspace.datasets[0]?await datasets.get(workspace.datasets[0].id):null,quarantines=selected&&selected.quarantined?await datasets.quarantines(selected.id):[],m=workspace.meta;
 return heading('02 / DATA INTAKE','数据接入与批次追溯','保留供稿原值、来源和内容指纹，按现行口径换算并隔离窗口不符记录。分析任务始终绑定一个不可变数据批次。')+'<div class="dataset-grid"><section class="panel"><div class="section-title"><h2>业务批次</h2><span>'+workspace.datasets.length+' 批</span></div><div class="batch-list">'+workspace.datasets.map(d=>'<button class="batch-item" data-dataset="'+d.id+'"><strong>'+esc(d.name)+' <em class="badge '+esc(d.lifecycle||'current')+'">'+esc(Lifecycle[d.lifecycle]||d.lifecycle||'现行')+'</em></strong><span>'+d.rows+' 条 · '+esc(d.source)+'</span><small>'+(d.spec?'口径 v'+d.spec.version+' · 窗口 '+d.spec.window_days+' 日':'未挂口径')+(d.quarantined?' · 隔离 '+d.quarantined+' 条':'')+'</small><small>SHA256 '+esc(d.checksum.slice(0,18))+'…</small></button>').join('')+'</div><div class="section-title"><h2>接入新数据</h2></div><form id="dataset-form"><label>批次名称<input name="name" required minlength="2" placeholder="例如：11 月复测批次"></label><label>上传 CSV 或 JSON<input type="file" id="file-input" accept=".json,.csv"></label><label>记录 JSON<textarea name="records" rows="6" placeholder="粘贴 JSON 数组，或先选择上方文件" required></textarea></label><p class="hint">字段：'+m.columns.map(c=>esc(c.key)+' / '+esc(c.label)).join('，')+'。5–5,000 条记录。'+(activeSpec?'现行口径 v'+activeSpec.version+'：观察窗口 '+activeSpec.window_days+' 日（可用 window_days 逐行标注，不符即隔离）；完成率接受百分数或小数（可用 completion_pct_unit 标注），原值保留并自动换算。':'')+'</p><button type="submit" class="primary" '+(session.user.role==='viewer'?'disabled':'')+'>校验并接入批次</button></form></section><section class="panel"><div class="section-title"><h2 id="preview-name">'+esc(selected?.name||'尚无批次')+'</h2><span>预览前 30 条 · 按现行口径换算后</span></div><div id="data-preview">'+table(m.columns,selected?.records.slice(0,30)||[])+'</div><div class="section-title"><h2>隔离记录</h2><span id="quar-count">'+(quarantines.length?quarantines.length+' 条被隔离':'')+'</span></div><div id="data-quarantines">'+quarView(quarantines)+'</div><div class="section-title"><h2>转换依据</h2><span>供稿原值 → 口径值</span></div><div id="data-provenance">'+provView(selected?.records||[])+'</div></section></div>';
}
export function bindData(refresh){
 let source='manual.json';
 document.querySelector('#file-input').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;source=file.name;const text=await file.text(),records=file.name.endsWith('.csv')?parseCSV(text):JSON.parse(text);document.querySelector('[name=records]').value=JSON.stringify(records,null,2);}catch(error){notify(error.message,true);}});
 document.querySelectorAll('[data-dataset]').forEach(button=>button.onclick=async()=>{try{const d=await datasets.get(button.dataset.dataset);const qs=d.quarantined?await datasets.quarantines(d.id):[];document.querySelector('#preview-name').textContent=d.name;document.querySelector('#data-preview').innerHTML=table(workspace.meta.columns,d.records.slice(0,30));document.querySelector('#quar-count').textContent=qs.length?qs.length+' 条被隔离':'';document.querySelector('#data-quarantines').innerHTML=quarView(qs);document.querySelector('#data-provenance').innerHTML=provView(d.records);}catch(error){notify(error.message,true);}});
 submit(document.querySelector('#dataset-form'),async f=>{const d=await datasets.create({name:f.get('name'),source,records:JSON.parse(f.get('records'))});notify('数据已接入：'+d.rows+' 条合格'+(d.quarantined?'，'+d.quarantined+' 条窗口不符被隔离':''));await refresh();});
}
