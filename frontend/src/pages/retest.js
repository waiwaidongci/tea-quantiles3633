import {retest} from '../api/retest.js';
import {table} from '../components/common/table.js';
import {esc} from '../utils/format.js';
import {bindForm} from '../hooks/forms.js';

const limits=x=>Object.entries(x||{}).map(([k,v])=>`${k}≥${v}`).join('，')||'—';
const indicators=x=>Object.entries(x||{}).map(([k,v])=>`${k} ${v}`).join('，')||'—';
const SAMPLE_STATUS={claimed:'已领',listed:'在生效单',free:'可配'};

function draftGroups(items){
 const m={};for(const it of items)(m[it.code]??=[]).push(it);
 return Object.entries(m).map(([code,list])=>`<p><strong>${esc(code)}</strong>　${list.map(it=>`${esc(it.batch)}/${esc(it.number)} <small>${it.claimed?'已领':'新配'}</small>`).join('、')}</p>`).join('')||'<p>尚无条目。</p>';
}

export async function render(){
 const s=await retest.state();
 const writer=['admin','analyst'].includes(localStorage.getItem('research-role'));
 const draft=s.draft,eff=s.effective;
 const draftStatus=!draft?'尚未编单':draft.stale?'<span class="error">草稿已过期：编单后发生领样或名额调整，需重新编单后才能发布</span>':`可发布 · 编单于 ${esc(draft.created_at)}`;
 const studyRows=s.studies.map(st=>[
  `${st.code} ${st.name}`,
  limits(st.limits),
  writer?{html:`<form id="quota-${st.id}" class="inline-form quota-form"><input name="quota" type="number" min="0" max="5000" value="${st.quota}" required><button type="submit">存</button></form>`}:st.quota,
  st.assigned,st.claimed,
  st.shortfall>0?{html:`<span class="error">欠 ${st.shortfall}</span>`}:'足额',
 ]);
 const effRows=(eff?.items??[]).map(it=>[
  it.code,`${it.batch}/${it.number}`,
  it.claimed?'已领':(writer?{html:`<button class="secondary claim" data-study="${it.study_id}" data-batch="${esc(it.batch)}" data-number="${esc(it.number)}">领样</button>`}:'未领'),
 ]);
 return `<div class="eyebrow">DAILY RETEST / 当日复测</div>
<h1>当日复测单 <small>${esc(s.day)}</small></h1>
<p>从已复核研究的冻结茶样中编单：按各研究指标下限与名额选样，同批同编号一天只能领用一次。先让拿满名额的研究尽可能多，再让入选总数尽可能多，平局按研究与茶样编号定序。名额调整后只重排未领茶样，发布时整单一次性切换。</p>
<h2>研究名额与欠额 <small>欠额 = 名额 − 生效单已配</small></h2>
${table(['研究','指标下限','名额','生效已配','已领','欠额'],studyRows)}
<h2>草稿单 <small>${draftStatus}</small></h2>
${writer?`<div class="toolbar"><button id="btn-compile">编单</button><button id="btn-publish" class="secondary" ${!draft||draft.stale?'disabled':''}>发布（整单切换）</button></div>`:''}
${draft?draftGroups(draft.items):'<p>尚无草稿，点击“编单”生成。</p>'}
<h2>生效单 <small>${eff?`第 ${eff.version} 版 · 发布于 ${esc(eff.published_at)}`:'尚未发布'}</small></h2>
${eff?table(['研究','茶样','领用'],effRows):'<p>发布草稿后生效。</p>'}
<h2>冻结茶样</h2>
${table(['批号','编号','指标','状态','持有研究'],s.samples.map(x=>[x.batch,x.number,indicators(x.indicators),SAMPLE_STATUS[x.status],x.holder??'—']))}
<h2>当日领用记录</h2>
${table(['研究','茶样','时间'],s.claims.map(c=>[c.code,`${c.batch}/${c.number}`,c.created_at]))}`;
}

export function bind(refresh){
 const notice=m=>{document.getElementById('notice').textContent=m;};
 const act=async fn=>{try{await fn();refresh();}catch(e){notice(e.message);}};
 document.getElementById('btn-compile')?.addEventListener('click',()=>act(()=>retest.compile()));
 document.getElementById('btn-publish')?.addEventListener('click',()=>act(()=>retest.publish()));
 document.querySelectorAll('.quota-form').forEach(form=>bindForm(form.id,async data=>{await retest.quota(Number(form.id.split('-')[1]),Number(data.quota));refresh();}));
 document.querySelectorAll('.claim').forEach(b=>b.addEventListener('click',()=>act(()=>retest.claim({study_id:Number(b.dataset.study),batch:b.dataset.batch,number:b.dataset.number}))));
}
