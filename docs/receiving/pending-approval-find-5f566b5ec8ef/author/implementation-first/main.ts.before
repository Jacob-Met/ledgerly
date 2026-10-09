import './style.css';
import './review.css';
import './intake-file.css';
import {createIntakeFileControls} from './intake-file-ui';
import type {IntakeFile} from './intake-file';
import './ledger-export.css';
import {createLedgerExport} from './ledger-export';
import './approval-preview.css';
import './invoice-details.css';
import {createInvoiceDetailsView} from './invoice-details';
import {createInvoiceRecordDownloads} from './invoice-record';
import './receivables.css';
import {createReceivablesView} from './receivables';
import {approvalListMarkup} from './approval-preview';
import './rejection-reason.css';
import {createRejectionReasons} from './rejection-reason';
import {readReviewFields, reviewLinesMarkup, reviewMarkup, reviewResultMarkup} from './review';
import {WorkerClient, WorkerUnavailableError} from './worker-client';
const $=<T extends HTMLElement>(selector:string)=>document.querySelector(selector) as T;
const ledgerExport=createLedgerExport($<HTMLButtonElement>('#ledger-export'),$<HTMLElement>('#ledger-export-note'));
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const invoiceDetails=createInvoiceDetailsView($<HTMLElement>('#ledger-list'));
const invoiceRecords=createInvoiceRecordDownloads($<HTMLElement>('#ledger-list'),status);
const receivables=createReceivablesView({mount:$<HTMLElement>('#receivables-view'),note:$<HTMLElement>('#receivables-note'),client:$<HTMLSelectElement>('#receivables-client'),due:$<HTMLSelectElement>('#receivables-due'),reset:$<HTMLButtonElement>('#receivables-reset'),summary:$<HTMLElement>('#receivables-summary'),list:$<HTMLElement>('#receivables-list')});
const rejectionReasons=createRejectionReasons($<HTMLElement>('#approval-list'));
const worker=new WorkerClient(()=>new Worker(new URL('./engine.worker.ts',import.meta.url),{type:'module'}),{
 ready:()=>status('Python loaded locally. No external service is connected.','ready'),
 unavailable:engineUnavailable,
});
let ready=false,busy=false,analysisResult:any=null,needsFreshSandbox=false,reviewNeedsAnalysis=false;
let reviewId:string|null=null,reviewEngaged=false,canReplay=false,rawDraftUsed=false;
const intakeFiles=createIntakeFileControls($<HTMLElement>('.intake'),{
 snapshot:()=>({sourceText:$<HTMLTextAreaElement>('#job-email').value,
  fields:$<HTMLFormElement>('#review-form')?readReviewFields($<HTMLFormElement>('#review-form')):null}),
 replace:replaceIntake,
});
async function replaceIntake(file:IntakeFile):Promise<boolean>{
 if(!ready||busy)return false;
 const previousForm=$<HTMLFormElement>('#review-form');
 reviewId=null;rawDraftUsed=false;reviewEngaged=Boolean(previousForm);reviewNeedsAnalysis=Boolean(previousForm);
 if(previousForm){
  $<HTMLInputElement>('#review-confirm').checked=false;
  $<HTMLElement>('#review-result').textContent='The old review is retired. The incoming source is being checked; existing input remains until that check completes.';
 }else analysisResult=null;
 syncControls();
 const reply=await runAction('analyze',{text:file.source_text});
 if(!reply?.ok){
  if(previousForm)$<HTMLElement>('#review-result').textContent='Opening did not complete. Your previous fields remain; confirm and check them again before drafting.';
  syncControls();return false;
 }
 $<HTMLTextAreaElement>('#job-email').value=file.source_text;
 renderAnalysis(reply.result);
 reviewNeedsAnalysis=false;
 if(file.review_fields){
  const fields=file.review_fields,form=$<HTMLFormElement>('#review-form');
  for(const name of ['client_name','client_email','due_days','amount_paid'] as const)
   (form.elements.namedItem(name) as HTMLInputElement).value=fields[name];
  $<HTMLElement>('#review-lines').innerHTML=reviewLinesMarkup(fields.line_items,reply.result.review_currencies||[]);
  markReviewDirty('Restored unfinished fields. Read the current original warnings, confirm your review and check these fields with Python.');
  $<HTMLDetailsElement>('#review-editor').open=true;
  $<HTMLInputElement>('#review-client-name').focus();
 }else $<HTMLDetailsElement>('#review-editor').querySelector<HTMLElement>('summary')?.focus();
 syncControls();return true;
}
function status(text:string,kind='info'){$<HTMLElement>('#status-message').textContent=text;$<HTMLElement>('#status-message').dataset.kind=kind;}
function call(action:string,payload:Record<string,unknown>={}){return worker.call(action,payload);}
function recoveryMessage(error:WorkerUnavailableError){return `${error.message} The in-memory sandbox is unavailable. Restart opens an empty sandbox. Your source email and correction fields stay here; no action will be replayed.`;}
function engineUnavailable(error:WorkerUnavailableError){
 intakeFiles.currentChanged('The Python session ended. Open the file again after reviewing your retained input.');
 const form=$<HTMLFormElement>('#review-form');
 needsFreshSandbox=true;reviewNeedsAnalysis=Boolean(form);reviewId=null;canReplay=false;rawDraftUsed=false;
 if(form){
  reviewEngaged=true;
  $<HTMLInputElement>('#review-confirm').checked=false;
  $<HTMLElement>('#review-result').textContent='The previous Python session ended. Your edits are retained; after restart, confirm and check them again.';
 }else{analysisResult=null;reviewEngaged=false;}
 setControls(false);
 for(const id of ['approval-list','ledger-list'])$<HTMLElement>(`#${id}`).setAttribute('aria-disabled','true');
 const start=$<HTMLButtonElement>('#engine-start');start.disabled=false;start.textContent='Restart empty sandbox';
 $<HTMLElement>('#engine-status').textContent='PYTHON UNAVAILABLE';$<HTMLElement>('#engine-dot').classList.remove('ready');
 $<HTMLElement>('#engine-note').textContent='The last displayed ledger is inactive. Restart creates an empty sandbox and keeps your source email and correction fields. No interrupted action is replayed.';
 const panel=$<HTMLElement>('#analysis');
 if(!form)panel.innerHTML='<p id="engine-recovery-analysis" class="empty"></p>';
 else if(!$<HTMLElement>('#engine-recovery-analysis'))panel.insertAdjacentHTML('afterbegin','<p id="engine-recovery-analysis" class="empty"></p>');
 $<HTMLElement>('#engine-recovery-analysis').textContent=form?'The Python session is unavailable. Your corrections are retained. Restart, then confirm and check them again.':'The Python session is unavailable. Your source email is still here. Restart, then analyze it again.';
 status(recoveryMessage(error),'error');
}
function analysisBlocked(ex:any){return !ex||ex.issues?.some((x:any)=>x.severity==='error')||(ex.confidence||0)<0.5||!ex.line_items?.length;}
function syncControls(){
 const enabled=ready&&!busy;
 rejectionReasons.setAvailability(ready,busy);
 intakeFiles.setAvailability(ready,busy);
 ledgerExport.setAvailable(enabled);
 invoiceDetails.setAvailability(ready,busy);
 receivables.setAvailability(ready,busy);
 for(const id of ['fixture-select','load-fixture','job-email','analyze','demo-date','advance-clock','run-chase','reset-sandbox','payment-amount'])$<HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement>(`#${id}`).disabled=!enabled;
 for(const el of Array.from(document.querySelectorAll<HTMLInputElement|HTMLSelectElement|HTMLButtonElement>('#review-form input,#review-form select,#review-form button,#approval-list button,#ledger-list button')))el.disabled=!enabled;
 invoiceRecords.setAvailability(ready,busy);
 const checked=$<HTMLInputElement>('#review-confirm');
 const check=$<HTMLButtonElement>('#review-check');if(check)check.disabled=!enabled||!checked?.checked;
 const draft=$<HTMLButtonElement>('#draft');draft.disabled=!enabled||(reviewEngaged?!reviewId:rawDraftUsed||analysisBlocked(analysisResult));
 draft.textContent=reviewEngaged?'Create reviewed sandbox draft':'Create sandbox draft';
 $<HTMLButtonElement>('#replay-webhook').disabled=!enabled||!canReplay;
}
function setControls(enabled:boolean){ready=enabled;syncControls();}
function invalidateAnalysis(message:string){
 intakeFiles.currentChanged();
 analysisResult=null;reviewId=null;reviewEngaged=false;rawDraftUsed=false;reviewNeedsAnalysis=false;
 $<HTMLElement>('#analysis').innerHTML=`<p class="empty">${esc(message)}</p>`;syncControls();
}
function markReviewDirty(message='Fields changed. Confirm your review and check them again.'){
 intakeFiles.currentChanged();
 reviewEngaged=true;reviewId=null;
 const check=$<HTMLInputElement>('#review-confirm');if(check)check.checked=false;
 const result=$<HTMLElement>('#review-result');if(result)result.textContent=message;
 syncControls();
}
function renderAnalysis(ex:any){
 intakeFiles.currentChanged();
 reviewId=null;reviewEngaged=false;rawDraftUsed=false;
 analysisResult=ex;const panel=$<HTMLElement>('#analysis'),items=ex.line_items||[],issues=ex.issues||[];
 const rows=items.map((x:any)=>`<tr><td>${esc(x.desc)}</td><td>${esc(x.qty??'Unclear')} ${esc(x.unit||'')}</td><td>${esc(x.currency||ex.currency||'')}</td><td>${esc(x.unit_price)}</td></tr>`).join('');
 const flags=issues.length?issues.map((x:any)=>`<li class="issue ${esc(x.severity)}"><b>${esc(String(x.severity).toUpperCase())} / ${esc(x.field)}</b><span>${esc(x.message)}</span></li>`).join(''):'<li class="issue info"><b>NO FLAGS</b><span>The rule validator found no issue.</span></li>';
 panel.innerHTML=`<div class="analysis-head"><div><span class="eyebrow">RULE EXTRACTOR / REAL OUTPUT</span><strong>${Math.round((ex.confidence||0)*100)}% confidence</strong></div><span class="source-chip">${esc(ex.source||'rules')}</span></div><div class="client-row"><span>${esc(ex.client_name||'Client name not found')}</span><span>${esc(ex.client_email||'Recipient email not found')}</span></div><div class="field-row"><span>CURRENCY</span><b>${esc(ex.currency||'Unclear')}</b><span>TERMS</span><b>${ex.due_days===0?'DUE ON RECEIPT':ex.due_days?`NET ${esc(ex.due_days)} DAYS`:'NOT FOUND'}</b></div><div class="item-table"><table><thead><tr><th>LINE ITEM</th><th>QTY</th><th>CCY</th><th>UNIT</th></tr></thead><tbody>${rows||'<tr><td colspan="4">No line items recognized.</td></tr>'}</tbody><tfoot><tr><td colspan="3">EXTRACTED TOTAL</td><td>${(ex.totals_by_currency||[{currency:ex.currency,total:ex.total}]).map((total:any)=>`${esc(total.currency||'')} ${esc(total.total||'0')}`).join('<br>')}</td></tr></tfoot></table></div><ul class="issue-list">${flags}</ul><p class="fine-print">Errors or low extraction confidence block drafting. Open the correction form to check the details yourself.</p>`;
 panel.insertAdjacentHTML('beforeend',reviewMarkup(ex));
 syncControls();
}function renderState(state:any){
 invoiceRecords.update(state);
 ledgerExport.setSnapshot(state);
 receivables.setSnapshot(state);
 canReplay=Boolean(state.can_replay);
 $<HTMLElement>('#mock-requests').textContent=String(state.mock_requests??0);$<HTMLElement>('#external-calls').textContent=String(state.external_calls??0);
 const dateInput=$<HTMLInputElement>('#demo-date');if(document.activeElement!==dateInput)dateInput.value=state.today||'';$<HTMLButtonElement>('#replay-webhook').disabled=!ready||!state.can_replay||busy;
 const queue=state.pending||[];$<HTMLElement>('#approval-list').innerHTML=approvalListMarkup(queue);
 rejectionReasons.afterRender(queue.map((action:any)=>action.id));
 const ledger=state.ledger||[];invoiceDetails.beforeRender(ledger.map((entry:any)=>entry.invoice_id));$<HTMLElement>('#ledger-list').innerHTML=ledger.length?ledger.map((e:any)=>{const open=['SENT','PARTIALLY_PAID','UNPAID'].includes(e.status)&&Number(e.balance)>0;return `<article class="invoice-card invoice-card-with-details" data-due="${esc(e.due_on||'')}"><div class="invoice-head"><div><span class="eyebrow">${esc(e.invoice_number)}</span><h3>${esc(e.client_name||e.client_email||'Client')}</h3></div><span class="status-chip ${esc(String(e.status).toLowerCase())}">${esc(e.status)}</span></div><div class="invoice-meta"><span>${esc(e.currency)} ${esc(e.total)}</span><span>PAID ${esc(e.paid_amount)}</span><span>BALANCE ${esc(e.balance)}</span></div><div class="invoice-meta"><span>DUE ${esc(e.due_on||'Terms missing')}</span><span>REMINDERS ${esc(e.reminders_sent)}</span></div>${open?`<button class="button button-payment" data-pay="${esc(e.invoice_id)}">Simulate sandbox payment</button>`:''}${invoiceDetails.markup(e.invoice_id,state)}${invoiceRecords.markup(e.invoice_id)}</article>`;}).join(''):'<p class="empty">No invoices in this sandbox ledger yet.</p>';
 invoiceDetails.afterRender();invoiceDetails.setAvailability(ready,busy);
 invoiceRecords.setAvailability(ready,busy);
 const audit=state.audit||[];$<HTMLOListElement>('#audit-list').innerHTML=audit.length?audit.map((e:any)=>`<li><span>${esc(e.event||'event')}</span><code>${esc(e.kind||e.tool||e.invoice||e.action||'')}</code><time>${esc((e.at||'').slice(11,19))}</time></li>`).join(''):'<li class="empty">Agent events will appear here as work runs.</li>';
}
async function runAction(name:string,payload:Record<string,unknown>={}){
 if(busy)return null;
 if(!ready&&name!=='init'){status('Load the local Python engine first.','error');return null;}
 if(['analyze','review','draft','reset'].includes(name))intakeFiles.currentChanged('An intake action started. Open the file again before replacing the current input.');
 busy=true;syncControls();
 try{
  const reply=await call(name,payload);
  if(reply.state)renderState(reply.state);
  if(!reply.ok){status(reply.message||reply.error||'The sandbox action failed.','error');return reply;}
  if(reply.result?.message)status(reply.result.message,'ready');else if(reply.result?.final)status(reply.result.final,'ready');
  return reply;
 }catch(error){status(error instanceof WorkerUnavailableError?recoveryMessage(error):String(error),'error');return null;}
 finally{busy=false;syncControls();}
}
$('#engine-start').addEventListener('click',async()=>{
 const b=$<HTMLButtonElement>('#engine-start'),restarting=needsFreshSandbox;b.disabled=true;
 status('Loading local Python and Ledgerly source...','loading');const reply=await runAction('init');
 if(reply?.ok){
  needsFreshSandbox=false;setControls(true);b.textContent='Python engine loaded';
  $<HTMLElement>('#engine-status').textContent='PYTHON READY / OFFLINE';$<HTMLElement>('#engine-dot').classList.add('ready');
  $<HTMLElement>('#engine-note').textContent='The sandbox stays in this tab. Close or reset it to discard its ledger.';
  const recovery=$<HTMLElement>('#engine-recovery-analysis');
  if(restarting&&recovery)recovery.textContent=reviewNeedsAnalysis?'New empty sandbox ready. Your corrections are retained; confirm and check them again.':'New empty sandbox ready. Analyze the retained source email again.';
  for(const id of ['approval-list','ledger-list'])$<HTMLElement>(`#${id}`).removeAttribute('aria-disabled');
  status(restarting?'New empty sandbox ready. Your source email and correction fields are preserved.':'Local sandbox ready. No external service is connected.','ready');
 }else{
  b.disabled=false;b.textContent=needsFreshSandbox?'Restart empty sandbox':'Retry loading engine';
  if(!needsFreshSandbox)$<HTMLElement>('#engine-note').textContent='Loading did not finish. Retry loading the engine when the runtime files are available. Your source email is preserved.';
 }
});
$('#load-fixture').addEventListener('click',async()=>{
 if(!ready||busy)return;busy=true;syncControls();
 try{const name=$<HTMLSelectElement>('#fixture-select').value;const r=await fetch(new URL(`fixtures/${name}`,new URL('./',window.location.href)));if(!r.ok)throw new Error(`Fixture HTTP ${r.status}`);$<HTMLTextAreaElement>('#job-email').value=await r.text();invalidateAnalysis('Fictional input loaded. Analyze it to review and correct its fields.');status('Fictional input loaded. Analyze it with the real Python rules.','ready');}
 catch(error){status(String(error),'error');}finally{busy=false;syncControls();}
});
$('#job-email').addEventListener('input',()=>invalidateAnalysis('Source text changed. Analyze it again before reviewing or drafting.'));
$('#analyze').addEventListener('click',async()=>{
 const text=$<HTMLTextAreaElement>('#job-email').value;if(!text.trim()){status('Paste or load a job email first.','error');return;}
 invalidateAnalysis('Running the Python rules on this source...');status('Running RulesExtractor in Python...','loading');
 const reply=await runAction('analyze',{text});if(reply?.ok){renderAnalysis(reply.result);const bad=analysisBlocked(reply.result);status(bad?'Open Review or correct invoice fields to resolve the blocking issue.':'Review extracted fields, then create the in-memory draft.','ready');}
});
$('#analysis').addEventListener('input',(event)=>{
 const target=event.target as HTMLInputElement;
 if(!target.closest('#review-form'))return;
 if(target.id==='review-confirm'){intakeFiles.currentChanged();reviewEngaged=true;reviewId=null;$<HTMLElement>('#review-result').textContent=target.checked?'Review confirmed. Check the fields with Python to prepare a draft.':'Confirm your review before checking the fields.';syncControls();return;}
 markReviewDirty();
});
$('#analysis').addEventListener('click',(event)=>{
 const button=(event.target as HTMLElement).closest<HTMLButtonElement>('#review-add-line,button[data-remove-line]');
 if(!button||busy)return;
 const form=$<HTMLFormElement>('#review-form'),fields=readReviewFields(form);
 if(button.id==='review-add-line')fields.line_items.push({desc:'',qty:'1',unit_price:'',currency:analysisResult.currency||'',unit:''});
 else fields.line_items.splice(Number(button.dataset.removeLine),1);
 markReviewDirty();$<HTMLElement>('#review-lines').innerHTML=reviewLinesMarkup(fields.line_items,analysisResult.review_currencies||[]);syncControls();
 if(button.id==='review-add-line')form.querySelector<HTMLInputElement>(`#review-line-${fields.line_items.length-1}-desc`)?.focus();
 else $<HTMLButtonElement>('#review-add-line').focus();
});
$('#analysis').addEventListener('submit',async(event)=>{
 const form=event.target as HTMLFormElement;if(form.id!=='review-form')return;event.preventDefault();
 if(busy||!$<HTMLInputElement>('#review-confirm').checked)return;
 reviewEngaged=true;reviewId=null;syncControls();
 const result=$<HTMLElement>('#review-result'),text=$<HTMLTextAreaElement>('#job-email').value,fields=readReviewFields(form);
 result.textContent='Checking the corrected fields with Python...';
 if(reviewNeedsAnalysis){
  const analyzed=await runAction('analyze',{text});
  if(!analyzed?.ok){result.textContent='The source could not be checked in the new sandbox. Your edits remain here.';return;}
  analysisResult=analyzed.result;reviewNeedsAnalysis=false;
 }
 const reply=await runAction('review',{text,fields,confirmed:true});
 if(reply?.ok){reviewId=reply.result.valid?reply.result.review_id:null;result.innerHTML=reviewResultMarkup(reply.result);if(reply.result.valid)$<HTMLElement>('#engine-recovery-analysis')?.remove();}
 else result.textContent=reply?.message||'The fields could not be checked. Your edits are still here.';
 syncControls();
});
$('#draft').addEventListener('click',async()=>{
 if(!analysisResult||busy||(reviewEngaged?!reviewId:rawDraftUsed||analysisBlocked(analysisResult)))return;
 const payload:Record<string,unknown>={text:$<HTMLTextAreaElement>('#job-email').value};
 if(reviewEngaged){payload.review_id=reviewId;reviewId=null;}else rawDraftUsed=true;
 status('Running Ledgerly Agent + RulePlanner against SandboxMock...','loading');
 const reply=await runAction('draft',payload);
 if(reply?.ok){
  status(reply.result.unauthorized_send_blocked?'Gate verified: an unapproved send was blocked. '+reply.result.final:reply.result.final,'ready');
  if(reviewEngaged){$<HTMLElement>('#review-result').textContent='This checked revision was used. Review its pending sandbox send in the human gate. To prepare a different draft, edit and check the fields again.';$<HTMLInputElement>('#review-confirm').checked=false;}
 }else if(reviewEngaged){$<HTMLElement>('#review-result').textContent='Drafting did not complete. Check the sandbox ledger before preparing another revision. Your edits remain here.';$<HTMLInputElement>('#review-confirm').checked=false;}
 syncControls();
});
$('#approval-list').addEventListener('click',async(event)=>{
 const b=(event.target as HTMLElement).closest<HTMLButtonElement>('button[data-approve],button[data-reject]');
 if(!b||busy||!ready)return;
 const approving=Boolean(b.dataset.approve),id=b.dataset.approve||b.dataset.reject||'';
 const payload:Record<string,unknown>={action_id:id};
 if(!approving){
  const reason=rejectionReasons.read(id);
  if(!reason.ok){status(reason.message,'error');return;}
  payload.reason=reason.value;
 }
 b.disabled=true;
 const reply=await runAction(approving?'approve':'reject',payload);
 if(reply?.ok)status(reply.result.approved?'Approved in the in-memory sandbox. No PayPal request was made.':`Rejected; nothing was sent. Reason: ${reply.result.reason}`,'ready');
});
$('#ledger-list').addEventListener('click',async(event)=>{const b=(event.target as HTMLElement).closest<HTMLButtonElement>('button[data-pay]');if(!b)return;b.disabled=true;const amount=$<HTMLInputElement>('#payment-amount').value.trim();const reply=await runAction('payment',{invoice_id:b.dataset.pay||'',amount:amount||null});if(reply?.ok)status(`Mock webhook verified: ${reply.result.from} -> ${reply.result.to}.`,'ready');});
$('#advance-clock').addEventListener('click',async()=>{const day=$<HTMLInputElement>('#demo-date').value;if(!day){status('Choose a date for the local clock.','error');return;}await runAction('advance',{day});});
$('#run-chase').addEventListener('click',async()=>{status('Running the overdue scan and reminder rules...','loading');await runAction('chase');});
$('#replay-webhook').addEventListener('click',async()=>{const reply=await runAction('replay');if(reply?.ok)status(reply.result.duplicate?'Duplicate webhook safely ignored by Ledgerly.':'Webhook processed.','ready');});
$('#reset-sandbox').addEventListener('click',async()=>{if(busy||!confirm('Discard the in-memory ledger and clear the pasted email?'))return;const reply=await runAction('reset');if(reply?.ok){$<HTMLTextAreaElement>('#job-email').value='';invalidateAnalysis('Sandbox reset. Load a fixture or paste a new email.');$<HTMLInputElement>('#payment-amount').value='';status('Sandbox reset. The in-memory ledger was cleared.','ready');}});
