import json
from datetime import date,datetime,time,timezone
from decimal import Decimal
from ledgerly.agent import Agent,RulePlanner,ApprovalRequired
from ledgerly.paypal import SandboxMock
from ledgerly.extract import PAYPAL_CURRENCIES, split_by_currency
from review import ReviewableExtractor, prepare_review
from review_history import completed_reviews
from invoice_details import snapshot_invoice_details
from uuid import uuid4

class Clock:
    def __init__(self): self.day=date.today()
    def __call__(self): return self.day

class Demo:
    def __init__(self):
        self.clock=Clock()
        self.mock=SandboxMock(now=lambda:datetime.combine(self.clock.day,time.min,tzinfo=timezone.utc))
        self.extractor=ReviewableExtractor()
        self.agent=Agent(self.mock,{"name":"Ledgerly Demo","email_address":"freelancer@example.test"},extractor=self.extractor,today=self.clock,webhook_verifier=self.mock.verify_webhook_signature)
        self.last_event=None
        self.analysis_text=None
        self.analysis=None
        self.review=None

    def draft(self, text):
        out=self.agent.run("invoice:"+text,RulePlanner());pending=out.get("pending",[]);blocked=[]
        for action in pending:
            if action.get("kind")=="send_invoice":
                try:self.agent.client.send_invoice(action["invoice_id"]);blocked.append(False)
                except ApprovalRequired:blocked.append(True)
        return {"final":out.get("final",""),"pending":pending,"unauthorized_send_blocked":bool(blocked) and all(blocked)}

    @staticmethod
    def totals(ex):
        return [{"currency":part.currency or "Unknown currency","total":str(part.total())} for part in split_by_currency(ex)]

    def snapshot(self):
        audit=[]
        for row in self.agent.audit[-18:]:
            audit.append({k:row[k] for k in ("at","event","action","kind","invoice","ok","event_type","from","to") if k in row})
        return {"today":self.clock.day.isoformat(),"ledger":[e.to_dict() for e in self.agent.ledger.values()],"invoice_details":snapshot_invoice_details(self.mock.invoices,self.agent.ledger),"pending":self.agent.list_pending(),"completed_reviews":completed_reviews(self.agent.pending.values()),"audit":audit,"mock_requests":len(self.mock.requests),"external_calls":0,"can_replay":self.last_event is not None}
    def dispatch(self,req):
        action=req.get("action")
        if action=="init": result={"ready":True,"engine":"RulesExtractor + RulePlanner + SandboxMock"}
        elif action=="analyze":
            self.review=None
            self.analysis=None
            if not isinstance(req.get("text",""),str):raise ValueError("Source email must be text.")
            self.analysis_text=req.get("text","")
            ex=self.agent.extractor.extract(self.analysis_text)
            self.analysis=ex.to_dict()
            result={**self.analysis,"review_currencies":sorted(PAYPAL_CURRENCIES),"totals_by_currency":self.totals(ex)}
        elif action=="review":
            self.review=None
            if self.analysis is None or req.get("text")!=self.analysis_text:
                raise ValueError("The source changed after analysis; analyze it again before reviewing.")
            if req.get("confirmed") is not True:
                raise ValueError("Review every invoice field and confirm the source warnings first.")
            ex=prepare_review(req.get("fields"))
            valid=not ex.errors and ex.confidence>=self.agent.min_confidence
            review_id=uuid4().hex if valid else None
            # Materialize every displayed value before admitting a draft revision.
            result={**ex.to_dict(),"valid":valid,"review_id":review_id,
                    "original_issues":self.analysis["issues"],
                    "totals_by_currency":self.totals(ex),
                    "message":"Fields checked. Create the reviewed draft, then approve its send separately." if valid else "Correct the remaining issues, then check the fields again."}
            if valid:self.review=(review_id,self.analysis_text,ex)
        elif action=="draft":
            text=req.get("text","")
            if "review_id" in req:
                checked=self.review
                self.review=None  # Consume before draft effects; never replay on retry.
                if checked is None or req["review_id"]!=checked[0] or text!=checked[1]:
                    raise ValueError("This checked revision is stale or already used; review and check it again.")
                _,source,ex=checked
                with self.extractor.using(source,ex):result=self.draft(text)
                result["reviewed"]=True
            else:result=self.draft(text)
        elif action=="approve":
            pending=next(a for a in self.agent.list_pending() if a["id"]==req["action_id"]);self.agent.approve(req["action_id"],approver="browser visitor");result={"approved":True,"kind":pending["kind"],"invoice_id":pending["invoice_id"]}
        elif action=="reject": self.agent.reject(req["action_id"],"Rejected by the browser visitor");result={"rejected":True}
        elif action=="payment":
            amount=req.get("amount");event=self.mock.simulate_payer_payment(req["invoice_id"],None if not amount else Decimal(str(amount)));raw=json.dumps(event,separators=(",",":")).encode("utf-8");headers=self.mock.sign(raw);self.last_event=(raw,headers);result=self.agent.handle_webhook(raw,headers)
        elif action=="replay": result={"ok":False,"message":"No webhook to replay."} if self.last_event is None else self.agent.handle_webhook(*self.last_event)
        elif action=="advance":
            new_day=date.fromisoformat(req["day"])
            if new_day<self.clock.day: raise ValueError("Demo clock only moves forward.")
            self.clock.day=new_day;result={"today":self.clock.day.isoformat()}
        elif action=="chase":
            # This fixed planner lists once, visits at most each current ledger entry,
            # then finishes. Keep the budget finite for this deterministic demo goal.
            steps=max(12,len(self.agent.ledger)+2)
            out=self.agent.run("chase",RulePlanner(),max_steps=steps)
            result={"final":out.get("final",""),"pending":out.get("pending",[])}
        elif action=="reset": self.__init__();result={"reset":True}
        else: raise ValueError("Unknown demo action.")
        return {"result":result,"state":self.snapshot()}

SESSION=Demo()
def handle_json(raw):
    try:
        response=SESSION.dispatch(json.loads(raw));return json.dumps({"ok":True,**response},default=str)
    except Exception as exc:
        return json.dumps({"ok":False,"error":type(exc).__name__,"message":str(exc),"state":SESSION.snapshot()},default=str)
