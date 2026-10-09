async () => {
 const groups=[], effects=[]; let actionEvents=[];
 const forbidden = name => (...args)=>{effects.push(name);throw new Error('forbidden '+name)};
 window.fetch=forbidden('fetch'); window.Worker=forbidden('Worker'); window.WebSocket=forbidden('WebSocket');
 XMLHttpRequest.prototype.open=forbidden('XHR'); Storage.prototype.setItem=forbidden('storage');
 navigator.sendBeacon=forbidden('beacon');
 const assert=(v,m)=>{if(!v)throw new Error(m)};
 const action=(id,kind,summary)=>({id,kind,invoice_id:'INV-'+id,summary,payload:kind==='send_reminder'?{subject:'Literal [.*] <tag>',note:'Straße Ω note'}:{invoice:{detail:{invoice_number:'N-'+id,note:'Nested [.*] <tag>'},primary_recipients:[{billing_info:{email_address:id+'@example.test'}}],items:[]}}});
 const a=action('A','send_invoice','Alpha'),b=action('B','send_reminder','Beta');
 function setup(queue=[a,b]){
  document.body.innerHTML='<input id="q"><select id="k"><option value="all">All</option><option value="send_invoice">Invoices</option><option value="send_reminder">Reminders</option></select><button id="c" type="button">Clear</button><p id="n"></p><p id="e" hidden>None</p><div id="l"></div>';
  const c={list:document.querySelector('#l'),query:document.querySelector('#q'),kind:document.querySelector('#k'),clear:document.querySelector('#c'),note:document.querySelector('#n'),empty:document.querySelector('#e')};
  c.list.innerHTML=window.peerRenderer.approvalListMarkup(queue);const ctl=window.peerFilter.createApprovalFilters(c);ctl.update(queue);ctl.setAvailability(true,false);
  const rows=()=>Array.from(c.list.querySelectorAll(':scope > .approval-card'));
  const query=t=>{c.query.value=t;c.query.dispatchEvent(new Event('input',{bubbles:true}))};
  const kind=t=>{c.kind.value=t;c.kind.dispatchEvent(new Event('change',{bubbles:true}))};
  return {c,ctl,rows,query,kind};
 }
 async function group(name,f){try{const details=await f();groups.push({name,passed:true,details})}catch(e){groups.push({name,passed:false,error:String(e)})}}
 await group('identity cohort rejects permutation, split, duplicate, unknown and malformed bindings',()=>{
  const results=[];
  for(const variant of ['permuted','split','duplicate-button','unknown-card','duplicate-queue']){
   const x=setup();x.query('Alpha');
   if(variant==='permuted')x.c.list.prepend(x.rows()[1]);
   if(variant==='split')x.rows()[0].querySelector('[data-reject]').dataset.reject='B';
   if(variant==='duplicate-button')x.rows()[0].append(x.rows()[0].querySelector('[data-approve]').cloneNode(true));
   if(variant==='unknown-card')x.rows()[0].dataset.approvalId='UNKNOWN';
   if(variant==='duplicate-queue')x.ctl.update([a,{...b,id:'A'}]);
   else x.query('Alpha');
   assert(x.rows().every(r=>!r.hidden),variant+' hid a mismatched card');assert(x.c.query.disabled&&x.c.kind.disabled,variant+' controls enabled');
   assert(x.c.query.value==='Alpha'&&x.c.note.textContent.includes('could not be matched'),variant+' lost retained state/refusal');
   results.push(variant);
  }return results;
 });
 await group('retire detached cards and recover invalid-to-current cohorts without losing query/type',()=>{
  const x=setup();x.query('Alpha');x.kind('send_invoice');const old=x.rows();
  x.ctl.update(null);assert(x.rows().every(r=>!r.hidden),'invalid hides');
  const q=[{...a,summary:'New current only'},{...b,id:'C',invoice_id:'INV-C',summary:'Alpha current'}];
  x.c.list.innerHTML=window.peerRenderer.approvalListMarkup(q);x.ctl.update(q);
  assert(x.c.query.value==='Alpha'&&x.c.kind.value==='send_invoice','lost filters');
  assert(x.rows().every(r=>r.hidden)&&!x.c.empty.hidden,'intersection wrong');
  old[0].querySelector('[data-approve]').dataset.approve='CORRUPTED-DETACHED';
  x.kind('all');assert(x.rows()[0].hidden&&!x.rows()[1].hidden,'old node or old text authority');
  assert(!x.c.query.disabled,'old detached corruption invalidated current');return {currentIds:x.rows().map(r=>r.dataset.approvalId),oldDetached:old.every(r=>!r.isConnected)};
 });
 await group('queue identity metadata copied and current rendered proposal text remains authoritative',()=>{
  const q=JSON.parse(JSON.stringify([a,b]));const x=setup(q);q[0].id='CHANGED';q[0].invoice_id='CHANGED';q[0].kind='send_reminder';
  x.query('INV-A');x.kind('send_invoice');assert(!x.rows()[0].hidden&&x.rows()[1].hidden,'caller changed captured metadata');
  x.query('CHANGED');assert(x.rows().every(r=>r.hidden),'mutation entered copied identity');
  x.rows()[0].querySelector('.approval-summary').textContent='Current rendered text';x.query('Current rendered text');assert(!x.rows()[0].hidden,'current literal text ignored');
  return {query:x.c.query.value,note:x.c.note.textContent};
 });
 await group('literal nested text, trimmed query and type intersection do not reinterpret markup',()=>{
  const x=setup();x.query(' [.*] <TAG> ');assert(x.rows().every(r=>!r.hidden),'literal or documented trim failed');
  assert(document.querySelectorAll('tag,script').length===0,'query inserted markup');
  x.kind('send_reminder');assert(x.rows()[0].hidden&&!x.rows()[1].hidden,'kind intersection');
  x.query('STRAẞE');assert(!x.rows()[1].hidden,'lowercase Unicode literal mismatch');
  x.query('.*not-regex');assert(x.rows().every(r=>r.hidden)&&!x.c.empty.hidden,'no-match state');
  x.c.clear.click();assert(x.c.query.value===''&&x.c.kind.value==='all'&&x.rows().every(r=>!r.hidden),'clear view');
  return {trimInterpretation:'leading/trailing whitespace ignored for matching; typed value retained until Clear'};
 });
 await group('busy and unavailable states retain view and refuse native disabled Clear',()=>{
  const x=setup();x.query('Beta');x.kind('send_reminder');
  const visible=x.rows().map(r=>!r.hidden);x.ctl.setAvailability(true,true);x.c.clear.click();
  assert(x.c.query.value==='Beta'&&x.c.kind.value==='send_reminder','busy Clear changed filters');assert(x.c.query.disabled&&x.c.clear.disabled,'busy controls');
  x.ctl.setAvailability(false,false);x.c.clear.click();assert(x.c.query.value==='Beta','unavailable Clear changed');
  assert(x.c.note.textContent.includes('inactive')&&JSON.stringify(x.rows().map(r=>!r.hidden))===JSON.stringify(visible),'unavailable state');
  x.ctl.setAvailability(true,false);assert(!x.c.query.disabled&&x.c.query.value==='Beta','ready state');
  return {note:x.c.note.textContent,visible};
 });
 await group('view events cause no effects and existing delegated button retains original ID',()=>{
  const queue=JSON.parse(JSON.stringify([a,b])),before=JSON.stringify(queue),x=setup(queue),nodes=x.rows();
  const strip=r=>{const c=r.cloneNode(true);c.removeAttribute('hidden');return c.outerHTML};
  const html=nodes.map(strip);x.c.list.addEventListener('click',e=>{const b=e.target.closest('button[data-approve],button[data-reject]');if(b)actionEvents.push({approve:b.dataset.approve??null,reject:b.dataset.reject??null})});
  x.query('Beta');x.kind('send_reminder');x.c.query.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));x.c.clear.click();
  assert(actionEvents.length===0&&effects.length===0,'filter caused an effect');assert(JSON.stringify(queue)===before,'queue mutated');assert(x.rows().every((r,i)=>r===nodes[i]&&strip(r)===html[i]),'card identity/markup mutated');
  nodes[1].querySelector('[data-reject]').click();assert(actionEvents.length===1&&actionEvents[0].reject==='B','original target mismatch');
  return {filterEffects:effects.slice(),originalDelegatedAction:actionEvents[0],queuePreserved:true,cardIdentityAndMarkupPreserved:true};
 });
 await group('empty accepted queue differs from no-match and does not replace renderer content',()=>{
  const x=setup([]),html=x.c.list.innerHTML;x.query('anything');assert(x.c.empty.hidden,'empty queue called no-match');assert(x.c.note.textContent.includes('0 of 0'),'empty count');
  x.c.clear.click();assert(x.c.list.innerHTML===html,'empty renderer replaced');return {note:x.c.note.textContent,originalMarkup:html};
 });
 return {groups,passed:groups.filter(g=>g.passed).length,total:groups.length,effects,actionEvents};
}
