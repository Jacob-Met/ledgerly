import json
from datetime import date,datetime,time,timezone
from decimal import Decimal
from ledgerly.agent import Agent,RulePlanner,ApprovalRequired
from ledgerly.paypal import SandboxMock

class Clock:
    def __init__(self): self.day=date.today()
    def __call__(self): return self.day

class Demo:
    def __init__(self):
        self.clock=Clock()
        self.mock=SandboxMock(now=lambda:datetime.combine(self.clock.day,time.min,tzinfo=timezone.utc))
        self.agent=Agent(self.mock,{"name":"Ledgerly Demo","email_address":"freelancer@example.test"},today=self.clock,webhook_verifier=self.mock.verify_webhook_signature)
        self.last_event=None

    def snapshot(self):
        audit=[]
        for row in self.agent.audit[-18:]:
            audit.append({k:row[k] for k in ("at","event","action","kind","invoice","ok","event_type","from","to") if k in row})
        return {"today":self.clock.day.isoformat(),"ledger":[e.to_dict() for e in self.agent.ledger.values()],"pending":self.agent.list_pending(),"audit":audit,"mock_requests":len(self.mock.requests),"external_calls":0,"can_replay":self.last_event is not None}
    def dispatch(self,req):
        action=req.get("action")
        if action=="init": result={"ready":True,"engine":"RulesExtractor + RulePlanner + SandboxMock"}
        elif action=="analyze": result=self.agent.extractor.extract(req.get("text","")).to_dict()
        elif action=="draft":
            out=self.agent.run("invoice:"+req.get("text",""),RulePlanner());pending=out.get("pending",[]);blocked=[]
            for action in pending:
                if action.get("kind")=="send_invoice":
                    try:self.agent.client.send_invoice(action["invoice_id"]);blocked.append(False)
                    except ApprovalRequired:blocked.append(True)
            result={"final":out.get("final",""),"pending":pending,"unauthorized_send_blocked":bool(blocked) and all(blocked)}
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
            out=self.agent.run("chase",RulePlanner());result={"final":out.get("final",""),"pending":out.get("pending",[])}
        elif action=="reset": self.__init__();result={"reset":True}
        else: raise ValueError("Unknown demo action.")
        return {"result":result,"state":self.snapshot()}

SESSION=Demo()
def handle_json(raw):
    try:
        response=SESSION.dispatch(json.loads(raw));return json.dumps({"ok":True,**response},default=str)
    except Exception as exc:
        return json.dumps({"ok":False,"error":type(exc).__name__,"message":str(exc),"state":SESSION.snapshot()},default=str)