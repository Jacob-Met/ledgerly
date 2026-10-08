import {describe,expect,it} from 'vitest';
import {hasIntakeCorrections} from '../src/intake-replacement';
import type {ReviewFields} from '../src/review';
const original:ReviewFields={client_name:'Example Ω',client_email:'a@example.test',due_days:'15',amount_paid:'0',line_items:[{desc:'Editing',qty:'2',unit_price:'100.00',currency:'USD',unit:'hours'},{desc:'Review',qty:'1',unit_price:'20',currency:'USD',unit:''}]};
describe('unfinished corrections require a replacement decision',()=>{
 it('leaves absent and byte-equivalent editable values on the ordinary path',()=>{
  expect(hasIntakeCorrections(null,original)).toBe(false);
  expect(hasIntakeCorrections(original,null)).toBe(false);
  expect(hasIntakeCorrections(structuredClone(original),original)).toBe(false);
 });
 it('retains changes to each recipient or terms field, including invalid unfinished values',()=>{
  for(const key of ['client_name','client_email','due_days','amount_paid'] as const){
   const edited=structuredClone(original);edited[key]='';expect(hasIntakeCorrections(edited,original)).toBe(true);
   edited[key]=original[key];expect(hasIntakeCorrections(edited,original)).toBe(false);
  }
 });
 it('notices every line field and exact decimal spelling rather than recalculating values',()=>{
  for(const key of ['desc','qty','unit_price','currency','unit'] as const){
   const edited=structuredClone(original);edited.line_items[0][key]+=' Ω';expect(hasIntakeCorrections(edited,original)).toBe(true);
  }
  const edited=structuredClone(original);edited.line_items[0].unit_price='100.0';expect(hasIntakeCorrections(edited,original)).toBe(true);
 });
 it('retains line order, added and removed lines and does not alter either input',()=>{
  const before=JSON.stringify(original),edited=structuredClone(original);edited.line_items.reverse();expect(hasIntakeCorrections(edited,original)).toBe(true);
  edited.line_items=[];expect(hasIntakeCorrections(edited,original)).toBe(true);
  edited.line_items=[...original.line_items,{...original.line_items[0]}];expect(hasIntakeCorrections(edited,original)).toBe(true);
  expect(JSON.stringify(original)).toBe(before);
 });
});
