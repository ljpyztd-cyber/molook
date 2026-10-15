/* Structure Viewer 1.1.0. Scientific records are immutable; viewers receive copies. */
'use strict';
const $ = id => document.getElementById(id);
const STATUS = {initial:'初始结构 · 未优化', illustrative:'示意构型', running:'优化中 · 未验收', accepted:'已验收 · 见证据', unverified:'待核验'};
const PALETTE = ['#477eaa','#c28a50','#9b6bb3','#338f83','#ab9a50','#7296b9','#bd7994','#7d8e57'];
const ELEMENT_COLORS = {H:'#d0d5dc',C:'#596779',N:'#4b74da',O:'#e6574f',F:'#3a9b81',Cl:'#3a9b81',S:'#e8b13e',P:'#e58b42',Si:'#bcad91',Cu:'#c4875a',Zn:'#8f9aac',Li:'#aa7eda',Na:'#a77bc7',Fe:'#ce8058',B:'#c3a296',Br:'#ad665a',I:'#986baa'};
let dataset, session, imported=[], selected=[], panels=new Map(), active=null, syncing=false, busy=false;
// Each panel starts with its own camera; linking is an explicit opt-in.
let settings={linked:false,style:'ball',color:'fragment',opacity:1,hydrogen:true,labels:true,cell:true,contacts:false};

function el(tag, text, cls) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; }
function option(value,text){ const o=el('option',text);o.value=value;return o; }
function tell(text){$('status').textContent=text;}
function fail(error){$('alert').hidden=false;$('alert').textContent=String(error.message||error);tell('操作未完成，请查看提示。');}
function clearError(){$('alert').hidden=true;}
function freeze(obj){ if(obj && typeof obj==='object'){Object.values(obj).forEach(freeze);Object.freeze(obj);}return obj; }
function allModels(){return [...dataset.models,...imported];}
function modelById(id){return allModels().find(m=>m.id===id);}
function frame(p){return p.model.frames[p.frameIndex];}
function fragmentInfo(p){ const f=frame(p), names=[...new Set(f.atoms.map(a=>a.fragment))]; return names.map((id,i)=>({id,title:p.model.fragments?.[id]?.title||id,color:p.model.fragments?.[id]?.color||PALETTE[i%PALETTE.length]})); }
function activePanel(){return panels.get(active);}
function isolated(action){const previous=syncing;syncing=true;try{return action();}finally{syncing=previous;}}
function visibleAtoms(p){ return frame(p).atoms.filter(a=>p.fragments.has(a.fragment) && (settings.hydrogen||a.element!=='H') && (!p.atomIds||p.atomIds.has(a.id))); }
function fmt(v,n=3){return Number(v).toFixed(n);}
async function post(path,value){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Preview-Token':session.token},body:JSON.stringify(value)});const d=await r.json();if(!r.ok)throw Error(d.error||'服务请求失败');return d;}

const vsub=(a,b)=>a.map((x,i)=>x-b[i]);
const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>Math.sqrt(dot(a,a));
function measureValue(type,atoms){
  const p=atoms.map(a=>a.position),length={distance:2,angle:3,dihedral:4}[type];
  if(p.length!==length)throw Error('该测量需要 '+length+' 个按顺序排列的原子 ID。');
  if(type==='distance')return norm(vsub(p[1],p[0]));
  if(type==='angle'){
    const a=vsub(p[0],p[1]),b=vsub(p[2],p[1]),d=norm(a)*norm(b);if(d<1e-12)throw Error('重合坐标使角度未定义。');
    return Math.acos(Math.max(-1,Math.min(1,dot(a,b)/d)))*180/Math.PI;
  }
  const b0=vsub(p[0],p[1]), b1=vsub(p[2],p[1]), b2=vsub(p[3],p[2]);
  const len=norm(b1);if(len<1e-12)throw Error('重合坐标使二面角未定义。');
  const u=b1.map(x=>x/len),a=b0.map((x,i)=>x-dot(b0,u)*u[i]),b=b2.map((x,i)=>x-dot(b2,u)*u[i]);
  if(norm(a)*norm(b)<1e-12)throw Error('共线原子使二面角未定义。');
  return Math.atan2(dot(cross(u,a),b),dot(a,b))*180/Math.PI;
}

function contactCandidates(p){
  const f=frame(p);if(p.contactCache?.key===f.id)return p.contactCache.values;
  if(f.atoms.length>5000)throw Error('接触筛选限 5,000 原子；请使用有明确片段划分的代表结构。');
  if(f.bond_mode!=='explicit')throw Error('接触筛选需要完整的显式 D–H 共价连接；此构型的连接信息不足。');
  const map=new Map(f.atoms.map(a=>[a.id,a])), neighbors=new Map(f.atoms.map(a=>[a.id,[]]));
  f.bonds.forEach(b=>{neighbors.get(b.a).push(map.get(b.b));neighbors.get(b.b).push(map.get(b.a));});
  const acceptors=f.atoms.filter(a=>['N','O','F'].includes(a.element)&&!neighbors.get(a.id).some(n=>n.element==='H'));
  const result=[];
  for(const d of f.atoms.filter(a=>['N','O','F'].includes(a.element))){
    for(const h of neighbors.get(d.id).filter(a=>a.element==='H'))for(const a of acceptors){
      if(a.fragment===d.fragment||a.id===d.id)continue;
      const ha=norm(vsub(h.position,a.position)),da=norm(vsub(d.position,a.position));
      if(ha>2.6||da>3.5||ha<1e-10)continue;
      const angle=measureValue('angle',[d,h,a]);
      if(angle>=130)result.push({d:d.id,h:h.id,a:a.id,ha,da,angle});
    }
  }
  p.contactCache={key:f.id,values:result};return result;
}

function newPanel(model){return {model,frameIndex:0,fragments:new Set(model.frames[0].atoms.map(a=>a.fragment)),atomIds:null,preset:'all',measurements:[],picked:[],viewer:null,initialView:null,contactCache:null};}
function initViewer(div){
  if(!window.$3Dmol)throw Error('离线 3Dmol.js 未加载；请检查 bundle 完整性。');
  const viewer=$3Dmol.createViewer(div,{backgroundColor:'white',antialias:true});
  viewer.setProjection('orthographic');return viewer;
}
function point(a){return {x:a.position[0],y:a.position[1],z:a.position[2]};}
function label(view,text,position,size,color='#304957'){view.addLabel(text,{position,font:'Arial',fontSize:size,fontColor:color,backgroundColor:'#ffffff',backgroundOpacity:.88,borderThickness:0,padding:3,inFront:true});}
function drawScene(p,viewer,labelSize=12,interactive=true){
  viewer.removeAllModels();viewer.removeAllShapes();viewer.removeAllLabels();
  const atoms=visibleAtoms(p),visible=new Map(atoms.map((a,i)=>[a.id,i])),frags=fragmentInfo(p),colors=new Map(frags.map(f=>[f.id,f.color]));
  const copies=atoms.map((a,i)=>({elem:a.element,x:a.position[0],y:a.position[1],z:a.position[2],serial:i+1,index:i,bonds:[],bondOrder:[],properties:{stableId:a.id,fragment:a.fragment,color:settings.color==='fragment'&&a.element==='C'?colors.get(a.fragment):(ELEMENT_COLORS[a.element]||'#879ba9')}}));
  for(const b of frame(p).bonds){if(visible.has(b.a)&&visible.has(b.b)){const i=visible.get(b.a),j=visible.get(b.b);copies[i].bonds.push(j);copies[i].bondOrder.push(b.order);copies[j].bonds.push(i);copies[j].bondOrder.push(b.order);}}
  const mol=viewer.addModel();mol.addAtoms(copies);
  const common={colorfunc:a=>a.properties.color,opacity:settings.opacity};
  const style=settings.style==='ball'?{sphere:{...common,scale:.26},stick:{...common,radius:.13}}:settings.style==='stick'?{sphere:{...common,scale:.12},stick:{...common,radius:.2}}:settings.style==='sphere'?{sphere:{...common,scale:.95}}:{line:{...common,linewidth:1.3},sphere:{...common,scale:.1}};
  mol.setStyle({},style);
  if(interactive)mol.setClickable({},true,a=>onAtom(p,atoms[visible.get(a.properties.stableId)]));
  if(settings.labels){
    for(const f of frags){const group=atoms.filter(a=>a.fragment===f.id);if(!group.length)continue;const c=[0,0,0];group.forEach(a=>a.position.forEach((x,j)=>c[j]+=x/group.length));label(viewer,f.title,{x:c[0],y:c[1]+.8,z:c[2]},labelSize,f.color);}
  }
  if(settings.cell&&frame(p).cell){
    const c=frame(p).cell,v=c.vectors,o=c.origin||[0,0,0],corners=[];
    for(let i=0;i<8;i++)corners.push({x:o[0]+((i&1)?v[0][0]:0)+((i&2)?v[1][0]:0)+((i&4)?v[2][0]:0),y:o[1]+((i&1)?v[0][1]:0)+((i&2)?v[1][1]:0)+((i&4)?v[2][1]:0),z:o[2]+((i&1)?v[0][2]:0)+((i&2)?v[1][2]:0)+((i&4)?v[2][2]:0)});
    for(let i=0;i<8;i++)for(const bit of [1,2,4])if(!(i&bit))viewer.addLine({start:corners[i],end:corners[i|bit],color:'#91a4b2',linewidth:1});
    ['a','b','c'].forEach((x,i)=>label(viewer,x+(c.periodic[i]?' (P)':' (NP)'),corners[1<<i],labelSize,'#728692'));
  }
  const map=new Map(frame(p).atoms.map(a=>[a.id,a]));
  if(settings.contacts&&frame(p).bond_mode==='explicit'&&frame(p).atoms.length<=5000){
    const contacts=contactCandidates(p).filter(c=>visible.has(c.d)&&visible.has(c.h)&&visible.has(c.a));
    for(const c of contacts.slice(0,300))viewer.addLine({start:point(map.get(c.h)),end:point(map.get(c.a)),color:'#319a99',dashed:true,dashLength:.16,gapLength:.11,linewidth:2});
  }
  for(const m of p.measurements){
    if(!m.ids.every(id=>visible.has(id)))continue;
    const ma=m.ids.map(id=>map.get(id));
    for(let i=1;i<ma.length;i++)viewer.addLine({start:point(ma[i-1]),end:point(ma[i]),color:'#ad5b91',dashed:true,linewidth:2});
    const c=ma.reduce((v,a)=>v.map((x,j)=>x+a.position[j]/ma.length),[0,0,0]);label(viewer,fmt(m.value)+(m.type==='distance'?' Å':'°'),{x:c[0],y:c[1],z:c[2]},labelSize,'#9b497f');
    ma.forEach(a=>label(viewer,a.id+' '+a.element,point(a),labelSize-1));
  }
  for(const id of p.picked){const a=map.get(id);if(a&&visible.has(id))label(viewer,'#'+id+' '+a.element,point(a),labelSize,'#226d70');}
  viewer.render();
}
function redraw(p){ return isolated(()=>{const view=p.viewer.getView();drawScene(p,p.viewer);p.viewer.setView(view);p.lastView=p.viewer.getView();updateCard(p);}); }
function safeFit(p,viewer,container,labelSize=12){
  const atoms=visibleAtoms(p);if(!atoms.length)return;
  const positions=atoms.map(a=>a.position),radius=settings.style==='sphere'?3:0.8;
  const low=[0,1,2].map(k=>Math.min(...positions.map(v=>v[k]))-radius),high=[0,1,2].map(k=>Math.max(...positions.map(v=>v[k]))+radius);
  if(settings.cell&&frame(p).cell){const c=frame(p).cell,o=c.origin||[0,0,0];for(let i=0;i<8;i++){const xyz=o.map((x,k)=>x+((i&1)?c.vectors[0][k]:0)+((i&2)?c.vectors[1][k]:0)+((i&4)?c.vectors[2][k]:0));xyz.forEach((v,k)=>{low[k]=Math.min(low[k],v);high[k]=Math.max(high[k],v);});}}
  viewer.zoomTo();const view=viewer.getView();for(let k=0;k<3;k++)view[k]=-(low[k]+high[k])/2;viewer.setView(view);viewer.render();
  const corners=[];for(let i=0;i<8;i++)corners.push({x:i&1?high[0]:low[0],y:i&2?high[1]:low[1],z:i&4?high[2]:low[2]});
  const screen=viewer.modelToScreen(corners),rect=container.getBoundingClientRect(),cx=rect.left+window.scrollX+rect.width/2,cy=rect.top+window.scrollY+rect.height/2;
  const halfX=Math.max(...screen.map(q=>Math.abs(q.x-cx))),halfY=Math.max(...screen.map(q=>Math.abs(q.y-cy))),margin=Math.max(20,labelSize*3.2);
  const factor=Math.min((rect.width/2-margin)/halfX,(rect.height/2-margin)/halfY);
  if(Number.isFinite(factor)&&factor>0)viewer.zoom(factor);viewer.render();
}
function fit(p,reset=false){
  return isolated(()=>{
  if(!visibleAtoms(p).length)return;
  if(reset&&p.initialView)p.viewer.setView(p.initialView);
  // zoomTo keeps orientation; padding leaves room for atom/fragment labels.
  safeFit(p,p.viewer,p.card.querySelector('.viewport'));
  p.lastView=p.viewer.getView();
  });
}
function dispose(viewer,container){
  if(viewer){viewer.setViewChangeCallback(()=>{});viewer.clear();}
  for(const canvas of container?.querySelectorAll('canvas')||[]){const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');gl?.getExtension('WEBGL_lose_context')?.loseContext();}
}

function rebuildCards(){
  return isolated(()=>{
  const previous=panels;const next=new Map();
  for(const id of selected){const p=previous.get(id)||newPanel(modelById(id));p.savedView=p.viewer?.getView()||p.savedView;next.set(id,p);}
  for(const p of previous.values())dispose(p.viewer,p.card);
  panels=next;$('cards').replaceChildren();$('cards').classList.toggle('single',selected.length===1);
  if(!selected.includes(active))active=selected[0];
  for(const [id,p] of panels){
    const card=el('article',undefined,'card');p.card=card;card.dataset.model=id;
    const head=el('div',undefined,'card-head'),titles=el('div');titles.append(el('h2',p.model.title||id));p.badge=el('span',undefined,'badge');titles.append(p.badge);
    const activate=el('button','操作此结构','activate');activate.onclick=()=>setActive(id);head.append(titles,activate);card.append(head);
    const bar=el('div',undefined,'frame-bar');bar.append(el('span','构型 / 帧'));
    const fs=el('select');fs.setAttribute('aria-label',(p.model.title||id)+' 构型帧');p.model.frames.forEach((f,i)=>fs.append(option(String(i),(i+1)+' · '+(f.title||f.id))));fs.value=String(p.frameIndex);
    fs.onchange=()=>isolated(()=>{clearError();p.frameIndex=+fs.value;p.fragments=new Set(frame(p).atoms.map(a=>a.fragment));p.atomIds=null;p.preset='all';p.measurements=[];p.picked=[];p.contactCache=null;drawScene(p,p.viewer);fit(p);setActive(id);updateCard(p);updateSources();tell('构型已切换；原子身份以该帧来源记录为准。');});bar.append(fs);card.append(bar);
    const view=el('div',undefined,'viewport');view.setAttribute('aria-label',(p.model.title||id)+' 可旋转三维结构');view.addEventListener('pointerdown',()=>setActive(id));card.append(view);
    p.foot=el('div',undefined,'card-foot');card.append(p.foot);$('cards').append(card);p.viewer=initViewer(view);
    drawScene(p,p.viewer);p.viewer.zoomTo();p.viewer.rotate(12,'x');p.viewer.rotate(-18,'y');safeFit(p,p.viewer,view);p.initialView=p.initialView||p.viewer.getView();
    if(p.savedView)p.viewer.setView(p.savedView);
    p.lastView=p.viewer.getView();
    p.viewer.setViewChangeCallback(()=>{
      const s=p.viewer.getView();if(p.lastView&&s.every((x,i)=>Math.abs(x-p.lastView[i])<1e-10))return;p.lastView=s.slice();
      if(!settings.linked||syncing||busy)return;
      syncing=true;try{for(const other of panels.values())if(other!==p&&other.viewer){const d=other.viewer.getView();for(let i=3;i<8;i++)d[i]=s[i];other.lastView=d.slice();other.viewer.setView(d);}}finally{syncing=false;}
    });updateCard(p);
  }
  $('compare-count').textContent=selected.length+' 个结构 · 正交投影';setActive(active);updateSources();
  });
}
function updateCard(p){
  const f=frame(p),shown=visibleAtoms(p),isFiltered=shown.length!==f.atoms.length;
  p.badge.textContent=STATUS[f.status];p.badge.className='badge '+f.status;
  p.foot.replaceChildren();const counts=el('div',undefined,'counts');counts.append(el('span',shown.length+' / '+f.atoms.length+' 原子'),el('span',f.bond_mode==='explicit'?'显式连接':f.bond_mode==='explicit-partial'?'部分显式连接':'无连接信息 · 仅原子'));p.foot.append(counts);
  const legend=el('div',undefined,'fragment-legend');fragmentInfo(p).filter(g=>p.fragments.has(g.id)).forEach(g=>{const s=el('span');const sw=el('i');sw.style.setProperty('--swatch',g.color);s.append(sw,document.createTextNode(g.title));legend.append(s);});p.foot.append(legend);
  let notes=[];if(isFiltered)notes.push('显示筛选：隐藏 '+(f.atoms.length-shown.length)+' 个原子，坐标不变。');
  if(p.preset!=='all')notes.push(p.model.presets?.find(x=>x.id===p.preset)?.note||'仅显示筛选，不是独立优化构型。');
  if(settings.contacts){try{notes.push('几何接触候选 '+contactCandidates(p).filter(c=>shown.some(a=>a.id===c.h)&&shown.some(a=>a.id===c.a)&&shown.some(a=>a.id===c.d)).length+' 条（最多显示 300 条）。');}catch(e){notes.push(e.message);}}
  if(!shown.length)notes.push('当前筛选没有可见原子。');
  if(f.atoms.length>5000)notes.push('大型结构：建议细线样式并关闭片段标签。');
  if(notes.length)p.foot.append(el('p',notes.join(' '),'card-note'));
}
function rebuildPicker(){
  $('model-picker').replaceChildren();for(const m of allModels()){
    const label=el('label',undefined,'model-pill'),check=el('input');check.type='checkbox';check.checked=selected.includes(m.id);check.setAttribute('aria-label','比较 '+(m.title||m.id));label.append(check,document.createTextNode(m.title||m.id));
    check.onchange=()=>{clearError();if(check.checked&&selected.length>=4){check.checked=false;fail('最多同时比较 4 个结构。请先取消一个结构。');return;}if(!check.checked&&selected.length===1){check.checked=true;return;}selected=check.checked?[...selected,m.id]:selected.filter(x=>x!==m.id);try{rebuildCards();}catch(e){fail(e);}};$('model-picker').append(label);
  }
}
function setActive(id){
  active=id;for(const [key,p] of panels)p.card.classList.toggle('active',key===id);const p=activePanel();if(!p)return;
  $('active-title').textContent=p.model.title||p.model.id;
  const presets=$('preset');presets.replaceChildren(option('all','全部片段'));for(const pr of p.model.presets||[])presets.append(option(pr.id,pr.title||pr.id));presets.value=p.preset;
  $('preset-note').textContent=p.preset==='all'?'筛选仅改变可见性，源坐标保持不变。':p.model.presets.find(x=>x.id===p.preset)?.note||'仅显示筛选。';
  $('fragments').replaceChildren();for(const g of fragmentInfo(p)){
    const l=el('label'),c=el('input');c.type='checkbox';c.checked=p.fragments.has(g.id);c.setAttribute('aria-label','显示片段 '+g.title);const sw=el('i');sw.style.setProperty('--swatch',g.color);l.append(c,sw,document.createTextNode(g.title));
    c.onchange=()=>{if(c.checked)p.fragments.add(g.id);else p.fragments.delete(g.id);p.preset='all';redraw(p);setActive(id);};$('fragments').append(l);
  }
  $('atom-filter').value=p.atomIds?[...p.atomIds].join(', '):'';updateMeasures();
}
function updateSources(){
  $('sources').replaceChildren();for(const p of panels.values()){
    const f=frame(p),row=el('div',undefined,'source-row');row.append(el('strong',p.model.title+' · '+STATUS[f.status]));
    row.append(el('div','来源：'+f.source.name+' · SHA256 '+f.source.sha256));row.append(el('div','坐标身份 SHA256：'+f.coordinate_sha256));
    if(f.acceptance_evidence)row.append(el('div','验收证据（提供者声明）：'+f.acceptance_evidence));
    for(const w of f.warnings||[])row.append(el('div',w));
    if(f.cell)row.append(el('div','周期性 a/b/c：'+f.cell.periodic.map(x=>x?'周期':'非周期').join(' / ')+'；只显示所列原子与原胞边框。'));
    $('sources').append(row);
  }
}
function inspect(p,a){
  if(!a)return;const g=fragmentInfo(p).find(g=>g.id===a.fragment);
  $('inspector').textContent=(p.model.title||p.model.id)+' · #'+a.id+' '+a.element+' · '+(g?.title||a.fragment)+' · 源坐标 ('+a.position.map(x=>fmt(x,6)).join(', ')+') Å'+(a.label?' · '+a.label:'');
}
function onAtom(p,a){
  clearError();setActive(p.model.id);inspect(p,a);const type=$('measure-mode').value;
  if(type==='inspect'){p.picked=[a.id];redraw(p);updateMeasures();return;}
  if(p.picked.length>={distance:2,angle:3,dihedral:4}[type])p.picked=[];
  if(!p.picked.includes(a.id))p.picked.push(a.id);$('measure-ids').value=p.picked.join(', ');
  if(p.picked.length==={distance:2,angle:3,dihedral:4}[type])try{addMeasurement(p,type,p.picked);}catch(e){fail(e);}
  redraw(p);updateMeasures();
}
function parseIds(text,allowRange=false){
  const ids=[];for(const token of text.split(/[,，;\s]+/).filter(Boolean)){
    const m=allowRange&&token.match(/^(\d+)-(\d+)$/);if(m){const a=+m[1],b=+m[2];if(b<a||b-a>50000)throw Error('原子编号范围无效。');for(let i=a;i<=b;i++)ids.push(String(i));}else ids.push(token);
  }return ids;
}
function addMeasurement(p,type,ids){
  const atoms=frame(p).atoms,map=new Map(atoms.map(a=>[a.id,a]));if(type==='inspect'){
    if(ids.length!==1)throw Error('识别模式请输入一个原子 ID，或选择距离 / 角度 / 二面角。');if(!map.has(ids[0]))throw Error('原子 ID 不存在。');p.picked=[ids[0]];inspect(p,map.get(ids[0]));return;
  }
  if(new Set(ids).size!==ids.length||ids.some(id=>!map.has(id)))throw Error('原子 ID 必须存在且不重复。');
  if(ids.some(id=>!visibleAtoms(p).some(a=>a.id===id)))throw Error('测量原子被筛选隐藏；先恢复这些原子的显示。');
  if(p.measurements.length>=30)throw Error('最多保留 30 条标注，请先清除部分测量。');
  const value=measureValue(type,ids.map(id=>map.get(id)));p.measurements.push({type,ids:[...ids],value});p.picked=[];tell('测量完成：'+fmt(value)+(type==='distance'?' Å':'°')+'（源坐标，非周期最小镜像）。');
}
function updateMeasures(){const p=activePanel();if(!p)return;$('picked').textContent=p.picked.length?'已选：'+p.picked.map(x=>'#'+x).join(' → '):'点击原子查看编号与坐标';$('measurements').replaceChildren();for(const m of p.measurements)$('measurements').append(el('li',m.ids.join(' → ')+' = '+fmt(m.value)+(m.type==='distance'?' Å':'°')));}

function currentView(){
  return {schema:'structure-viewer-view/1',dataset_sha256:session.dataset_sha256,settings:{...settings},selected:[...selected],active,importedModels:imported,panels:[...panels.values()].map(p=>({model:p.model.id,frame:frame(p).id,coordinate_sha256:frame(p).coordinate_sha256,fragments:[...p.fragments],atomIds:p.atomIds?[...p.atomIds]:null,preset:p.preset,measurements:p.measurements,view:p.viewer.getView()}))};
}
function validateImportedModel(m){
  if(!m?.id||!Array.isArray(m.frames)||!m.frames.length)throw Error('恢复文件含无效模型。');
  for(const f of m.frames){if(!Array.isArray(f.atoms)||f.atoms.length>50000||!f.source?.sha256||!f.coordinate_sha256||!STATUS[f.status])throw Error('恢复文件含无效构型。');const ids=new Set();for(const a of f.atoms){if(typeof a.id!=='string'||ids.has(a.id)||!Array.isArray(a.position)||a.position.length!==3||!a.position.every(Number.isFinite)||typeof a.fragment!=='string')throw Error('恢复文件含无效原子。');ids.add(a.id);}for(const b of f.bonds||[])if(!ids.has(b.a)||!ids.has(b.b))throw Error('恢复文件连接无效。');}
}
async function restoreView(value){
  if(value.schema!=='structure-viewer-view/1'||value.dataset_sha256!==session.dataset_sha256)throw Error('视图与当前数据集的 SHA256 不匹配，拒绝恢复。');
  // Imported coordinates are revalidated on the server before entering the scene.
  const extras=value.importedModels||[];for(const m of extras)validateImportedModel(m);
  const restoredImports=extras.length?(await post('/api/restore-imports',{models:extras})).models:[];
  const restoredModels=[...dataset.models,...restoredImports];
  if(!Array.isArray(value.selected)||value.selected.length<1||value.selected.length>4||new Set(value.selected).size!==value.selected.length||value.selected.some(id=>!restoredModels.some(m=>m.id===id)))throw Error('恢复文件的面板选择无效。');
  const s=value.settings;if(!s||!['ball','stick','sphere','line'].includes(s.style)||!['fragment','element'].includes(s.color)||!Number.isFinite(s.opacity)||s.opacity<.15||s.opacity>1)throw Error('恢复文件显示设置无效。');
  for(const k of ['linked','hydrogen','labels','cell','contacts'])if(typeof s[k]!=='boolean')throw Error('恢复文件显示开关无效。');
  const ready=new Map();
  for(const id of value.selected){
    const saved=value.panels.find(p=>p.model===id),p=newPanel(restoredModels.find(m=>m.id===id));if(!saved)throw Error('缺少面板状态。');p.frameIndex=p.model.frames.findIndex(f=>f.id===saved.frame);if(p.frameIndex<0||frame(p).coordinate_sha256!==saved.coordinate_sha256)throw Error('构型身份不匹配。');
    if(!Array.isArray(saved.view)||saved.view.length!==8||!saved.view.every(Number.isFinite))throw Error('无效相机视图。');
    const ids=new Set(frame(p).atoms.map(a=>a.id)),frags=new Set(frame(p).atoms.map(a=>a.fragment));
    if(!Array.isArray(saved.fragments)||saved.fragments.some(f=>!frags.has(f))||saved.atomIds?.some(id=>!ids.has(id)))throw Error('恢复文件筛选无效。');
    p.fragments=new Set(saved.fragments);p.atomIds=saved.atomIds?new Set(saved.atomIds):null;p.preset=saved.preset;p.savedView=saved.view;
    const atomMap=new Map(frame(p).atoms.map(a=>[a.id,a]));
    p.measurements=(saved.measurements||[]).slice(0,30).map(m=>({type:m.type,ids:m.ids,value:measureValue(m.type,m.ids.map(id=>{if(!atomMap.has(id))throw Error('测量编号无效。');return atomMap.get(id);} ))}));ready.set(id,p);
  }
  for(const p of panels.values())dispose(p.viewer,p.card);panels=ready;imported=restoredImports.map(freeze);settings={...s};selected=[...value.selected];active=value.active;syncControls();rebuildPicker();rebuildCards();tell('视图已恢复；构型与坐标身份哈希一致。');
}
function syncControls(){for(const k of ['linked','hydrogen','labels','cell','contacts'])$(k).checked=settings[k];for(const k of ['style','color','opacity'])$(k).value=settings[k];$('opacity-value').textContent=Math.round(settings.opacity*100)+'%';}

function wrapText(ctx,text,x,y,width,lineHeight){
  let line='';for(const ch of String(text)){if(ch==='\n'||ctx.measureText(line+ch).width>width){ctx.fillText(line,x,y);y+=lineHeight;line=ch==='\n'?'':ch;}else line+=ch;}ctx.fillText(line,x,y);return y+lineHeight;
}
function exportRecords(list){return list.map(p=>{const f=frame(p),visible=new Set(visibleAtoms(p).map(a=>a.id));return {model:p.model.id,title:p.model.title,frame:f.id,status:f.status,acceptance_evidence:f.acceptance_evidence||null,source:f.source,coordinate_sha256:f.coordinate_sha256,visible_atom_ids:[...visible],hidden_atom_count:f.atoms.length-visible.size,preset:p.preset,measurements:p.measurements,contacts:settings.contacts&&f.bond_mode==='explicit'&&f.atoms.length<=5000?contactCandidates(p).filter(c=>visible.has(c.d)&&visible.has(c.h)&&visible.has(c.a)):[],bond_mode:f.bond_mode,warnings:f.warnings||[],cell:f.cell||null};});}
async function exportPNG(onlyActive){
  if(busy)return;clearError();busy=true;for(const id of ['export-all','export-active','quick-export'])$(id).disabled=true;document.querySelectorAll('main,header,.comparison-bar').forEach(n=>n.inert=true);tell('正在重新渲染高清 PNG…');
  let temporary=null,tempViewer=null;
  try{
    const list=onlyActive?[activePanel()]:[...panels.values()],exportedViews=[];if(list.some(p=>!visibleAtoms(p).length))throw Error('存在空面板；请恢复可见原子后导出。');
    const width=+$('resolution').value,cols=Math.min(2,list.length),rows=Math.ceil(list.length/cols),imageHeight=Math.round(width*.7),header=150,cellHeight=imageHeight+360;
    const canvas=document.createElement('canvas');canvas.width=width*cols;canvas.height=header+rows*cellHeight+80;const ctx=canvas.getContext('2d');
    ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#223847';ctx.font='600 '+Math.round(width/48)+'px "Segoe UI", "Microsoft YaHei", sans-serif';wrapText(ctx,dataset.title,40,48,canvas.width-80,38);
    ctx.font=Math.round(width/78)+'px "Segoe UI", "Microsoft YaHei", sans-serif';ctx.fillStyle='#687b88';wrapText(ctx,'STRUCTURE REVIEW · 源坐标只读 · 显示筛选不代表优化结果 · 长度 Å / 角度 °',40,104,canvas.width-80,32);
    for(let i=0;i<list.length;i++){
      const p=list[i],f=frame(p),x=(i%cols)*width,y=header+Math.floor(i/cols)*cellHeight;
      temporary=el('div',undefined,'export-surface');temporary.style.width=width+'px';temporary.style.height=imageHeight+'px';document.body.append(temporary);tempViewer=initViewer(temporary);drawScene(p,tempViewer,Math.round(width/90),false);tempViewer.setView(p.viewer.getView());if($('export-fit').checked)safeFit(p,tempViewer,temporary,Math.round(width/90));tempViewer.render();
      exportedViews.push({model:p.model.id,frame:f.id,view:tempViewer.getView(),viewport:[width,imageHeight]});
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));const image=new Image();image.src=tempViewer.pngURI();await image.decode();
      ctx.fillStyle='#223847';ctx.font='600 '+Math.round(width/58)+'px "Segoe UI", "Microsoft YaHei", sans-serif';wrapText(ctx,String.fromCharCode(65+i)+'  '+p.model.title,x+40,y+40,width-80,34);
      ctx.font=Math.round(width/78)+'px "Segoe UI", "Microsoft YaHei", sans-serif';ctx.fillStyle=f.status==='accepted'?'#34755c':'#986c28';wrapText(ctx,STATUS[f.status]+' | '+f.title,x+40,y+85,width-80,29);
      ctx.drawImage(image,x,y+110,width,imageHeight);dispose(tempViewer,temporary);temporary.remove();temporary=null;tempViewer=null;
      let fy=y+imageHeight+142;ctx.font=Math.round(width/90)+'px "Segoe UI", "Microsoft YaHei", sans-serif';ctx.fillStyle='#526c7d';
      const shown=visibleAtoms(p).length;fy=wrapText(ctx,shown+' / '+f.atoms.length+' 原子 · '+(shown<f.atoms.length?'筛选隐藏，坐标不变；并非独立优化结果':'全部原子')+' · '+(f.bond_mode==='absent'?'无连接信息':'显式连接'),x+40,fy,width-80,27);
      fy=wrapText(ctx,'来源 '+f.source.name+' | SHA256 '+f.source.sha256.slice(0,16)+'…',x+40,fy,width-80,27);
      fy=wrapText(ctx,'坐标 SHA256 '+f.coordinate_sha256.slice(0,24)+'… | 构型 '+f.id,x+40,fy,width-80,27);
      const legends=fragmentInfo(p).filter(g=>p.fragments.has(g.id));let lx=x+40;for(const g of legends){const text=g.title,tw=ctx.measureText(text).width+43;if(lx+tw>x+width-40){fy+=29;lx=x+40;}ctx.fillStyle=g.color;ctx.fillRect(lx,fy-14,13,13);ctx.fillStyle='#526c7d';ctx.fillText(text,lx+20,fy);lx+=tw;}fy+=30;
      if(settings.contacts)fy=wrapText(ctx,'青色虚线：几何接触候选。D–H 显式；H···A ≤2.6 Å，D···A ≤3.5 Å，角度 ≥130°。',x+40,fy,width-80,27);
      if(p.measurements.length)wrapText(ctx,'紫色：源坐标测量，非周期最小镜像；完整原子 ID / 数值见 PNG 元数据及同名 JSON。',x+40,fy,width-80,27);
      ctx.strokeStyle='#dce5e8';ctx.strokeRect(x+18,y+5,width-36,cellHeight-12);
    }
    ctx.font='20px "Segoe UI", "Microsoft YaHei", sans-serif';ctx.fillStyle='#6b7f8b';ctx.fillText('Structure Viewer '+session.version+' · '+new Date().toISOString()+' · '+($('export-fit').checked?'各面板独立适配；非同一比例尺 · ':'当前相机 · ')+'完整来源 / 状态 / 相机随 PNG 与 JSON 保存',40,canvas.height-28);
    const metadata={...currentView(),export_kind:onlyActive?'single':'comparison',export_fit:$('export-fit').checked,exported_views:exportedViews,pixel_size:[canvas.width,canvas.height],records:exportRecords(list),measurement_convention:'Cartesian source coordinates, no minimum-image convention',contact_criterion:'Explicit D-H, D/A=N/O/F; A without bonded H; different fragments; HA<=2.6 A, DA<=3.5 A, DHA>=130 degrees; geometric candidates only'};
    const result=await post('/api/export',{kind:'png',data:canvas.toDataURL('image/png'),metadata});showExport(result);tell('PNG 已保存：'+result.path);
  }catch(e){fail(e);}finally{if(temporary){dispose(tempViewer,temporary);temporary.remove();}busy=false;document.querySelectorAll('main,header,.comparison-bar').forEach(n=>n.inert=false);for(const id of ['export-all','export-active','quick-export'])$(id).disabled=false;}
}
function showExport(result){$('export-result').replaceChildren();const a=el('a','打开 '+result.name);a.href=result.url;a.target='_blank';a.rel='noopener';$('export-result').append(a,el('div',result.path));}

function bind(){
  $('linked').onchange=()=>{settings.linked=$('linked').checked;tell(settings.linked?'相机联动：同步旋转与缩放，保留各结构中心。':'相机可独立操作。');};
  for(const k of ['style','color','opacity','hydrogen','labels','cell','contacts'])$(k).onchange=()=>{
    clearError();const old=settings[k];settings[k]=['hydrogen','labels','cell','contacts'].includes(k)?$(k).checked:k==='opacity'?+$(k).value:$(k).value;
    try{for(const p of panels.values())redraw(p);syncControls();}catch(e){settings[k]=old;syncControls();fail(e);}
  };
  $('fit-all').onclick=()=>{syncing=true;try{for(const p of panels.values())fit(p);}finally{syncing=false;}};
  $('reset-all').onclick=()=>{syncing=true;try{for(const p of panels.values()){p.viewer.setView(p.initialView);fit(p);}}finally{syncing=false;}};
  $('preset').onchange=()=>{const p=activePanel(),pr=p.model.presets?.find(x=>x.id===$('preset').value);p.preset=pr?.id||'all';p.fragments=new Set(pr?pr.fragments:frame(p).atoms.map(a=>a.fragment));p.atomIds=null;redraw(p);setActive(active);};
  $('apply-filter').onclick=()=>{clearError();try{const p=activePanel(),ids=parseIds($('atom-filter').value,true),available=new Set(frame(p).atoms.map(a=>a.id));if(ids.some(id=>!available.has(id)))throw Error('筛选包含不存在的原子 ID。');p.atomIds=ids.length?new Set(ids):null;redraw(p);}catch(e){fail(e);}};
  $('clear-filter').onclick=()=>{const p=activePanel();p.fragments=new Set(frame(p).atoms.map(a=>a.fragment));p.atomIds=null;p.preset='all';redraw(p);setActive(active);};
  $('measure-mode').onchange=()=>{const p=activePanel();p.picked=[];$('measure-ids').value='';redraw(p);updateMeasures();};
  $('measure').onclick=()=>{clearError();try{const p=activePanel();addMeasurement(p,$('measure-mode').value,parseIds($('measure-ids').value));redraw(p);updateMeasures();}catch(e){fail(e);}};
  $('clear-measurements').onclick=()=>{const p=activePanel();p.measurements=[];p.picked=[];redraw(p);updateMeasures();};
  $('export-all').onclick=()=>exportPNG(false);$('export-active').onclick=()=>exportPNG(true);
  $('quick-export').onclick=()=>exportPNG(false);
  $('save-view').onclick=async()=>{clearError();try{const result=await post('/api/export',{kind:'view',metadata:currentView()});showExport(result);tell('视图已保存：'+result.path);}catch(e){fail(e);}};
  $('restore-file').onchange=async e=>{clearError();try{const file=e.target.files[0];if(file){if(file.size>8*1024*1024)throw Error('视图文件超过 8 MiB。');await restoreView(JSON.parse(await file.text()));}}catch(err){fail(err);}finally{e.target.value='';}};
  $('import-file').onchange=async e=>{clearError();try{const file=e.target.files[0];if(!file)return;if(file.size>32*1024*1024)throw Error('交互导入限 32 MiB。请通过 CLI 选择代表帧。');tell('正在校验导入结构…');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));const r=await post('/api/import',{name:file.name,data_base64:btoa(binary)});const models=[...allModels(),r.model];if(models.length>100||models.reduce((n,m)=>n+m.frames.reduce((s,f)=>s+f.atoms.length,0),0)>250000)throw Error('当前数据集达到容量上限；请建立独立预览。');imported.push(freeze(r.model));if(selected.length<4)selected.push(r.model.id);rebuildPicker();rebuildCards();tell('结构已导入，状态：待核验。原始字节副本保存在 bundle/imports。');}catch(err){fail(err);}finally{e.target.value='';}};
  const resize=new ResizeObserver(()=>{if(busy)return;isolated(()=>{for(const p of panels.values()){p.viewer.resize();p.viewer.render();p.lastView=p.viewer.getView();}});});resize.observe($('cards'));
  window.addEventListener('error',e=>{if(e.message&&!e.message.includes('ResizeObserver'))fail(e.message);});
  let interaction=Date.now();document.addEventListener('pointerdown',()=>interaction=Date.now(),{passive:true});document.addEventListener('keydown',()=>interaction=Date.now(),{passive:true});
  setInterval(()=>{if(document.visibilityState==='visible'&&Date.now()-interaction<90000)fetch('/api/session').catch(()=>{});},60000);
}

async function main(){
  try{
    const results=await Promise.all([fetch('dataset.json').then(r=>{if(!r.ok)throw Error('数据集读取失败');return r.json();}),fetch('/api/session').then(r=>{if(!r.ok)throw Error('请通过本地服务打开预览');return r.json();})]);
    dataset=freeze(results[0]);session=results[1];if(dataset.schema!=='structure-viewer/1')throw Error('不支持的数据契约版本');
    $('title').textContent=dataset.title||'结构预览';document.title=$('title').textContent;$('description').textContent=dataset.description||'本地结构检查与比较';
    selected=dataset.models.slice(0,Math.min(2,dataset.models.length)).map(m=>m.id);active=selected[0];rebuildPicker();rebuildCards();syncControls();bind();
    tell('已加载 '+dataset.models.length+' 个结构 · 输出：'+session.export_path+' · 闲置 '+session.idle_minutes+' 分钟自动停止');
  }catch(e){fail(e);}
}
main();
