import {expect, it} from 'vitest';
import {approvalMatches, createApprovalFilters} from '../src/approval-filter';

function fixture(queue = [
  {id:'A', invoice_id:'INV-A', kind:'send_invoice', payload:{note:'untouched'}},
  {id:'B', invoice_id:'INV-B', kind:'send_reminder', payload:{note:'untouched'}},
]) {
  const control = (value = '') => ({value, disabled:false, hidden:false, textContent:'', handlers:{} as Record<string,()=>void>,
    addEventListener(type:string,fn:()=>void){this.handlers[type]=fn;}});
  const card = (id:string,text:string) => {
    const approve={dataset:{approve:id}},reject={dataset:{reject:id}};
    return {dataset:{approvalId:id},hidden:false,text,
      querySelectorAll(selector:string):any[]{
        if(selector==='button[data-approve]')return [approve];
        if(selector==='button[data-reject]')return [reject];
        return [{textContent:text}];
      },approve,reject};
  };
  let rows=queue.map((a,i)=>card(a.id,i===0?'Zoë <img> USD 001.20 [draft]':'Alpha reminder message'));
  const controls={list:{querySelectorAll:()=>rows},query:control(),kind:control('all'),clear:control(),note:control(),empty:control()};
  const filters=createApprovalFilters(controls as any);
  filters.update(queue);filters.setAvailability(true,false);
  return {controls,filters,queue,rows:()=>rows,replace:(next:typeof rows)=>{rows=next;},card,
    search:(q:string)=>{controls.query.value=q;controls.query.handlers.input();},
    kind:(k:string)=>{controls.kind.value=k;controls.kind.handlers.change();}};
}

it('matches literal case-insensitive text, trimmed boundaries, Unicode and exact decimal spelling',()=>{
  expect(approvalMatches('Zoë <img> USD 001.20 [draft]','send_invoice',' ZOË ','all')).toBe(true);
  expect(approvalMatches('Zoë <img> USD 001.20 [draft]','send_invoice','[draft]','all')).toBe(true);
  expect(approvalMatches('Zoë <img> USD 001.20 [draft]','send_invoice','.*','all')).toBe(false);
  expect(approvalMatches('USD 001.20','send_invoice','1.2','all')).toBe(true);
  expect(approvalMatches('USD 001.20','send_invoice','USD 1.20','all')).toBe(false);
});
it('intersects type and text without sorting, replacing nodes, changing payloads or buttons',()=>{
  const f=fixture(),before=JSON.stringify(f.queue),rows=f.rows(),buttons=rows.map(x=>[x.approve,x.reject]);
  f.search('inv-b');f.kind('send_invoice');expect(rows.map(x=>x.hidden)).toEqual([true,true]);
  expect(f.controls.empty.hidden).toBe(false);f.kind('send_reminder');
  expect(rows.map(x=>x.hidden)).toEqual([true,false]);expect(f.controls.note.textContent).toContain('1 of 2');
  expect(f.rows()).toBe(rows);expect(rows.map(x=>[x.approve,x.reject])).toEqual(buttons);
  expect(JSON.stringify(f.queue)).toBe(before);
});
it('finds detached action and invoice IDs and clears only view state',()=>{
  const f=fixture();f.search('a');f.kind('send_invoice');expect(f.rows().map(x=>x.hidden)).toEqual([false,true]);
  f.search('INV-B');expect(f.rows().every(x=>x.hidden)).toBe(true);
  f.controls.clear.handlers.click();expect(f.controls.query.value).toBe('');expect(f.controls.kind.value).toBe('all');
  expect(f.rows().every(x=>!x.hidden)).toBe(true);expect(f.queue).toHaveLength(2);
});
it('retains query/type across accepted snapshot replacement and retires old nodes',()=>{
  const f=fixture();f.search('alpha');f.kind('send_reminder');const old=f.rows();
  const fresh=[f.card('C','Alpha current reminder')];f.replace(fresh);
  f.filters.update([{id:'C',invoice_id:'INV-C',kind:'send_reminder'}]);
  expect(f.controls.query.value).toBe('alpha');expect(f.controls.kind.value).toBe('send_reminder');
  expect(fresh[0].hidden).toBe(false);expect(f.controls.note.textContent).toContain('1 of 1');
  f.search('no match');expect(fresh[0].hidden).toBe(true);expect(old[1].hidden).toBe(false);
});
it('refuses an equal-count permuted DOM and restores every current card',()=>{
  const f=fixture();f.search('none');f.replace([...f.rows()].reverse());f.search('anything');
  expect(f.rows().every(x=>!x.hidden)).toBe(true);expect(f.controls.query.disabled).toBe(true);
  expect(f.controls.note.textContent).toContain('could not be matched');
});
it('refuses split approve/reject identities even when card identity is correct',()=>{
  const f=fixture();f.rows()[0].reject.dataset.reject='B';f.search('none');
  expect(f.rows().every(x=>!x.hidden)).toBe(true);expect(f.controls.kind.disabled).toBe(true);
});
it('refuses duplicated and malformed queue identities, then recovers without clearing filters',()=>{
  const f=fixture();f.search('alpha');f.kind('send_reminder');
  f.filters.update([f.queue[0],f.queue[0]]);expect(f.rows().every(x=>!x.hidden)).toBe(true);
  f.filters.update([{id:'A',invoice_id:123,kind:'send_invoice'},f.queue[1]]);expect(f.controls.query.disabled).toBe(true);
  f.filters.update(f.queue);expect(f.controls.query.disabled).toBe(false);
  expect(f.controls.query.value).toBe('alpha');expect(f.rows().map(x=>x.hidden)).toEqual([true,false]);
});
it('copies accepted metadata instead of retaining a mutable queued object',()=>{
  const f=fixture();f.queue[0].id='mutated';f.queue[0].invoice_id='changed';f.search('INV-A');
  expect(f.rows().map(x=>x.hidden)).toEqual([false,true]);
});
it('truthfully disables during busy/unavailable while preserving filters and queue nodes',()=>{
  const f=fixture();f.search('alpha');f.kind('send_reminder');
  f.filters.setAvailability(true,true);expect(f.controls.query.disabled).toBe(true);
  expect(f.controls.note.textContent).toContain('Python is working');
  f.filters.setAvailability(false,false);expect(f.controls.clear.disabled).toBe(true);
  expect(f.controls.note.textContent).toContain('inactive');expect(f.controls.empty.hidden).toBe(true);
  f.filters.setAvailability(true,false);expect(f.controls.query.value).toBe('alpha');
  expect(f.controls.kind.value).toBe('send_reminder');expect(f.controls.query.disabled).toBe(false);
});
it('accepts an empty queue without claiming no matches, with explicit clear resetting view',()=>{
  const f=fixture([]);f.search('retained');expect(f.controls.note.textContent).toContain('0 of 0');
  expect(f.controls.empty.hidden).toBe(true);f.filters.clear();expect(f.controls.query.value).toBe('');
});
it('leaves unknown action kinds available in All pending and excludes them only by explicit type',()=>{
  const f=fixture([{id:'X',invoice_id:'INV-X',kind:'future_kind',payload:{note:'untouched'}}]);
  expect(f.rows()[0].hidden).toBe(false);f.kind('send_invoice');expect(f.rows()[0].hidden).toBe(true);
  f.kind('all');expect(f.rows()[0].hidden).toBe(false);
});
it('invalid select values fail open and a clear restores a valid association',()=>{
  const f=fixture();f.kind('unexpected');expect(f.rows().every(x=>!x.hidden)).toBe(true);
  expect(f.controls.query.disabled).toBe(true);f.controls.clear.handlers.click();
  expect(f.controls.query.disabled).toBe(false);
});
