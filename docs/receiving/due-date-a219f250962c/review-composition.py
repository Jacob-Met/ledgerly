"""Independent PR13/current-main composition challenges; SandboxMock only."""
import sys,json,hashlib,unittest
from pathlib import Path
from dataclasses import fields
from datetime import date
from decimal import Decimal

ROOT=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]) if len(sys.argv)>2 else None
sys.path.insert(0,str(ROOT))
from ledgerly.agent import Agent,LedgerEntry,RulePlanner,ApprovalRequired
from ledgerly.paypal import SandboxMock

FIXTURE=(ROOT/'fixtures/01_simple_usd_hourly.txt').read_text()
PREFIX=['invoice_id','invoice_number','client_name','client_email','currency','total','due_days',
        'status','sent_on','paid_amount','reminders_sent','last_reminder_on','prepaid',
        'provider_due_on','provider_due_known']

class Clock:
    day=date(2026,10,1)
    def __call__(self):return self.day

class CreateOnly:
    def next_step(self,goal,history,tools):
        if any(h['role']=='tool' for h in history):return {'final':'Draft prepared for human approval.'}
        return {'tool':'create_invoice','args':{'text':goal}}

class CompositionReview(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.mock=SandboxMock()
        self.agent=Agent(self.mock,{'name':'Independent reviewer','email_address':'reviewer@example.test'},today=self.clock)

    def drafted(self):
        run=self.agent.run(FIXTURE.replace('Net 15','Net 12'),CreateOnly())
        tool_steps=[h for h in run['history'] if h['role']=='tool']
        self.assertEqual([h['tool'] for h in tool_steps],['create_invoice'])
        self.assertTrue(tool_steps[0]['result']['ok'],tool_steps)
        row=tool_steps[0]['result']['invoices'][0]
        self.assertFalse(any(m=='GET' for m,p,b in self.mock.requests))
        return row,self.agent.ledger[row['invoice_id']]

    def reminders(self):
        return [b for m,p,b in self.mock.requests if m=='POST' and p.endswith('/remind')]

    def test_create_only_planner_preserves_serialized_date_and_enters_reminder_gate(self):
        row,entry=self.drafted()
        term=self.mock.invoices[row['invoice_id']]['detail']['payment_term'].copy()
        self.assertEqual(term,{'term_type':'DUE_ON_DATE_SPECIFIED','due_date':'2026-10-13'})
        self.assertIsNone(entry.due_on)
        self.assertFalse(entry.provider_due_known)
        with self.assertRaises(ApprovalRequired):self.agent.client.send_invoice(row['invoice_id'])
        self.clock.day=date(2026,10,8)
        self.agent.approve(row['approval_id'])
        self.assertEqual(entry.sent_on,date(2026,10,8))
        self.assertEqual(entry.due_on,date(2026,10,13),'actual serialized draft deadline must survive omitted status read')
        self.assertFalse(entry.provider_due_known)
        self.assertEqual(self.mock.invoices[row['invoice_id']]['detail']['payment_term'],term)
        self.clock.day=date(2026,10,13)
        self.assertEqual(self.agent.tool_list_overdue()['overdue'],[])
        self.clock.day=date(2026,10,14)
        rows=self.agent.tool_list_overdue()['overdue']
        self.assertEqual([(r['invoice_id'],r['days_overdue']) for r in rows],[(row['invoice_id'],1)])
        self.agent.run('chase',RulePlanner())
        pending=self.agent.list_pending()
        self.assertEqual([p['kind'] for p in pending],['send_reminder'])
        self.assertIn('Oct 13, 2026',pending[0]['payload']['note'])
        self.assertEqual(self.reminders(),[])
        self.assertEqual(sum(m=='POST' and p.endswith('/send') for m,p,b in self.mock.requests),1)

    def test_provider_date_and_explicit_absence_still_override_retained_deadline(self):
        row,entry=self.drafted()
        self.clock.day=date(2026,10,8)
        self.agent.approve(row['approval_id'])
        inv=self.mock.invoices[row['invoice_id']]
        inv['detail']['payment_term']={'term_type':'DUE_ON_DATE_SPECIFIED','due_date':'2026-10-30'}
        self.agent.tool_get_status(row['invoice_id'])
        self.assertTrue(entry.provider_due_known)
        self.assertEqual(entry.due_on,date(2026,10,30))
        if hasattr(entry,'invoice_due_on'):self.assertEqual(entry.invoice_due_on,date(2026,10,13))
        self.clock.day=date(2026,10,31)
        drafted=self.agent.tool_send_reminder(row['invoice_id'])
        self.assertTrue(drafted['ok'])
        stale_id=drafted['approval_id']
        old_note=self.agent.pending[stale_id].payload['note']
        self.assertIn('Oct 30, 2026',old_note)
        inv['detail']['payment_term']={'term_type':'NO_DUE_DATE'}
        with self.assertRaises(ValueError):self.agent.approve(stale_id)
        self.assertIsNone(entry.due_on)
        self.assertTrue(entry.provider_due_known)
        self.assertEqual(self.agent.pending[stale_id].status,'REJECTED')
        self.assertEqual(self.agent.pending[stale_id].payload['note'],old_note)
        self.assertEqual(self.reminders(),[])
        inv['detail']['payment_term']={'term_type':'DUE_ON_DATE_SPECIFIED','due_date':'2026-10-03'}
        fresh=self.agent.tool_send_reminder(row['invoice_id'])
        self.assertTrue(fresh['ok'])
        self.assertNotEqual(fresh['approval_id'],stale_id)
        self.assertEqual(entry.due_on,date(2026,10,3))
        self.assertIn('Oct 03, 2026',fresh['draft']['note'])
        self.assertEqual(self.reminders(),[])
        self.assertEqual(self.agent.client._permits,set())

    def test_incomplete_provider_refresh_cannot_erase_observed_or_retained_fact(self):
        row,entry=self.drafted()
        self.clock.day=date(2026,10,8)
        self.agent.approve(row['approval_id'])
        inv=self.mock.invoices[row['invoice_id']]
        inv['detail']['payment_term']={'term_type':'DUE_ON_DATE_SPECIFIED','due_date':'2026-11-07'}
        self.agent.tool_get_status(row['invoice_id'])
        before=entry.to_dict()
        anchor=getattr(entry,'invoice_due_on',None)
        inv['detail']['payment_term']={'term_type':'DUE_ON_DATE_SPECIFIED'}
        inv['status']='CANCELLED'
        with self.assertRaises(ValueError):self.agent.tool_get_status(row['invoice_id'])
        self.assertEqual(entry.to_dict(),before)
        self.assertEqual(getattr(entry,'invoice_due_on',None),anchor)
        self.assertTrue(entry.provider_due_known)
        self.assertEqual(entry.provider_due_on,date(2026,11,7))
        self.assertEqual(self.agent.list_pending(),[])
        self.assertEqual(self.reminders(),[])
        self.assertEqual(self.agent.client._permits,set())

    def test_current_main_positional_fields_and_observed_absence_keep_meaning(self):
        names=[f.name for f in fields(LedgerEntry)]
        self.assertEqual(names[:len(PREFIX)],PREFIX)
        if 'invoice_due_on' in names:self.assertEqual(names[len(PREFIX):],['invoice_due_on'])
        values=['INV-REVIEW','LDG-REVIEW','Reviewer','reviewer@example.test','USD',Decimal('91'),12,
                'SENT',date(2026,10,8),Decimal('11'),2,date(2026,10,7),Decimal('5'),None,True]
        entry=LedgerEntry(*values)
        self.assertEqual([getattr(entry,n) for n in PREFIX],values)
        self.assertIsNone(entry.due_on,'observed NO_DUE_DATE is a fact, not a missing fallback')
        entry.provider_due_on=date(2026,12,1)
        self.assertEqual(entry.due_on,date(2026,12,1))
        entry.provider_due_known=False
        self.assertEqual(entry.due_on,date(2026,10,20),'legacy entries with no saved draft use the old send-date fallback')

suite=unittest.defaultTestLoader.loadTestsFromTestCase(CompositionReview)
result=unittest.TextTestRunner(verbosity=2).run(suite)
data=(ROOT/'ledgerly/agent.py').read_bytes()
receipt={'source_root':str(ROOT),'agent_sha256':hashlib.sha256(data).hexdigest(),
    'agent_git_blob':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),
    'tests_run':result.testsRun,'failures':[{'test':t.id(),'detail':trace} for t,trace in result.failures],
    'errors':[{'test':t.id(),'detail':trace} for t,trace in result.errors],
    'success':result.wasSuccessful(),'effects':'SandboxMock only; zero external calls; reminders never approved'}
if OUT:OUT.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
