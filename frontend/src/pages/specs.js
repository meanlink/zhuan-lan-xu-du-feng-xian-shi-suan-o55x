import {specs,reversions,datasets} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {status} from '../components/common/status.js';
import {PlanStatus,ItemStatus,SpecStatus} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
export async function specPage(){
 const [specList,plans,batches]=await Promise.all([specs.list(),reversions.list(),datasets.list()]);
 workspace.specs=specList;
 const active=specList.filter(s=>s.status==='active'),current=batches.filter(d=>d.lifecycle==='current'),canWrite=session.user.role!=='viewer',first=active[0];
 return heading('03 / SPEC & REVERSION','供稿口径与批次换版','口径声明字段、单位与观察窗口；接入保留原值并按口径换算，窗口不符即隔离。修订口径后可对已有批次立案换版，全部校验成功才一次性切换新试验入口。')
 +'<div class="spec-grid"><section class="panel"><div class="section-title"><h2>口径版本</h2><span>'+specList.length+' 个版本</span></div><div class="spec-list">'
 +specList.map(s=>'<article><div><strong>'+esc(s.family)+' · v'+s.version+'</strong> '+status(s.status,SpecStatus)+'<p>观察窗口 '+s.window_days+' 日 · '+s.fields.length+' 个字段'+(s.note?' · '+esc(s.note):'')+'</p><small>'+date(s.created_at)+'</small></div>'+(s.status==='active'?'<button class="button small" data-base="'+s.id+'" '+(canWrite?'':'disabled')+'>以此为底稿修订</button>':'')+'</article>').join('')
 +'</div><div class="section-title"><h2>修订口径</h2><span>保存即生成下一版本，旧版同时废止</span></div><form id="spec-form"><label>口径族<input name="family" required minlength="2" value="'+esc(first?first.family:'')+'"></label><label>观察窗口（日）<input type="number" name="window_days" min="1" max="60" value="'+(first?first.window_days:14)+'" required></label><label>字段声明 JSON<textarea name="fields" rows="9" required>'+esc(first?JSON.stringify(first.fields,null,2):'')+'</textarea></label><label>修订说明<input name="note" maxlength="500" placeholder="例如：完成率标签明确为百分数写法"></label><button type="submit" class="primary" '+(canWrite?'':'disabled')+'>保存为新版本</button><p class="hint">字段须恰好覆盖模型契约字段；完成率标准单位固定为百分数(0~100)，可声明接受小数供稿并自动换算；观察窗口不符的记录在接入时被隔离并保留原因。</p></form></section>'
 +'<section class="panel"><div class="section-title"><h2>立案换版</h2><span>冻结原批次与目标版本</span></div><form id="reversion-form"><label>换版案名称<input name="name" required minlength="2" value="口径换版案"></label><label>目标口径<select name="target_spec_id">'+active.map(s=>'<option value="'+s.id+'">'+esc(s.family)+' · v'+s.version+' · 窗口 '+s.window_days+' 日</option>').join('')+'</select></label><div class="check-list">'+current.map(d=>'<label class="check"><input type="checkbox" name="src" value="'+d.id+'"><span>'+esc(d.name)+' <small>'+(d.spec?'口径 v'+d.spec.version:'未挂口径')+' · '+d.rows+' 条</small></span></label>').join('')+'</div><button type="submit" class="primary" '+(canWrite&&active.length&&current.length?'':'disabled')+'>立案并后台执行</button><p class="hint">同一原批次仅允许一个进行中的换版案，后到案不予受理；逐批生成替代批次，全部校验成功才切换新试验入口，任一失败保留旧版；中断按进度恢复，重试不新增替代批次。</p></form>'
 +'<div class="section-title"><h2>换版案</h2><span>'+plans.length+' 案 · <button class="text-button" id="refresh-plans">刷新 ↻</button></span></div><div class="plan-list">'
 +plans.map(p=>'<article class="plan"><div class="plan-head"><strong>'+esc(p.name)+'</strong>'+status(p.status,PlanStatus)+'</div><p>目标口径 v'+esc(p.spec_version)+' · 窗口 '+esc(p.window_days)+' 日 · 进度 '+p.progress.converted+'/'+p.progress.total+' · '+date(p.created_at)+'</p><ul class="item-list">'
   +p.items.map(i=>'<li><span>'+esc(i.source_name||'批次#'+i.source_dataset_id)+' → '+esc(i.replacement_name||'（未生成）')+'</span><small>'+esc(ItemStatus[i.status]||i.status)+(i.attempts>1?' · 第 '+i.attempts+' 次执行':'')+(i.error?' · '+esc(i.error):'')+'</small></li>').join('')
   +'</ul>'+(p.error?'<p class="warning">'+esc(p.error)+'</p>':'')+(p.status==='failed'?'<button class="button small" data-retry="'+p.id+'" '+(canWrite?'':'disabled')+'>按进度重试</button>':'')+'</article>').join('')
 +(plans.length?'':'<p class="empty">尚无换版案。修订口径后，可对已有现行批次立案换版。</p>')+'</div></section></div>';
}
export function bindSpecs(refresh){
 document.querySelectorAll('[data-base]').forEach(b=>b.onclick=()=>{const s=workspace.specs.find(x=>x.id===Number(b.dataset.base));if(!s)return;const f=document.querySelector('#spec-form');f.family.value=s.family;f.window_days.value=s.window_days;f.fields.value=JSON.stringify(s.fields,null,2);f.note.focus();notify('已载入 v'+s.version+' 为底稿');});
 submit(document.querySelector('#spec-form'),async f=>{let fields;try{fields=JSON.parse(f.get('fields'));}catch(e){throw new Error('字段声明不是有效 JSON');}await specs.create({family:f.get('family'),fields,window_days:Number(f.get('window_days')),note:f.get('note')||''});notify('已保存为新口径版本');await refresh();});
 submit(document.querySelector('#reversion-form'),async f=>{const ids=f.getAll('src').map(Number);if(!ids.length)throw new Error('请至少勾选一个原批次');await reversions.create({name:f.get('name'),source_dataset_ids:ids,target_spec_id:Number(f.get('target_spec_id'))});notify('换版案已受理，后台逐批执行');await refresh();});
 document.querySelector('#refresh-plans')?.addEventListener('click',refresh);
 document.querySelectorAll('[data-retry]').forEach(b=>b.onclick=async()=>{try{await reversions.retry(b.dataset.retry);notify('已重新排队，按进度继续');await refresh();}catch(e){notify(e.message,true);}});
}
