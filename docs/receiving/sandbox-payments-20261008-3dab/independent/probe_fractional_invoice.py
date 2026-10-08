"""Independent actual bridge receipt: currency-rounded invoice remains payable."""
from pathlib import Path
from datetime import date
from decimal import Decimal
import sys, json, importlib.util, os, copy
os.environ["LEDGERLY_ALLOW_NETWORK"]="0"
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root),str(root/"web-demo/python")]
import urllib.request,socket
def blocked(*a,**k): raise RuntimeError("network forbidden in authored fixture")
urllib.request.urlopen=blocked
socket.create_connection=blocked
import ledgerly.paypal as paypal
paypal.HttpPayPalClient.__init__=blocked
spec=importlib.util.spec_from_file_location("review_payment_bridge",root/"web-demo/python/bridge.py")
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
demo=bridge.Demo();demo.clock.day=date(2026,10,8);bridge.SESSION=demo
text=(root/"fixtures/02_gbp_proofreading.txt").read_text().replace("18 hours @ £40/hr","1.5 hours @ £0.01/hr").replace("Style sheet preparation: 2 hrs @ £40/hr\n","")
def request(**kw): return json.loads(bridge.handle_json(json.dumps(kw)))
draft=request(action="draft",text=text)
if not draft["ok"]: raise RuntimeError(draft)
pending=draft["state"]["pending"][0]
approved=request(action="approve",action_id=pending["id"])
if not approved["ok"]: raise RuntimeError(approved)
invoice_id=pending["invoice_id"]
before=copy.deepcopy(demo.mock.invoices[invoice_id])
first=request(action="payment",invoice_id=invoice_id,amount="0.01")
after=copy.deepcopy(demo.mock.invoices[invoice_id])
result={"subject":str(root),"input_text":text,"draft_result":draft["result"],"before":before,"first_result":first,"after":after}
if first["ok"]:
 result["final_result"]=request(action="payment",invoice_id=invoice_id)
 result["final_invoice"]=copy.deepcopy(demo.mock.invoices[invoice_id])
Path(sys.argv[2]).write_text(json.dumps(result,indent=2,default=str)+"\n")
print(json.dumps({"marker":"FRACTIONAL_INVOICE_RECEIPT","subject":root.name,"quantity":before["items"][0]["quantity"],"unit_amount":before["items"][0]["unit_amount"]["value"],"invoice_amount":before["amount"]["value"],"payment_ok":first["ok"],"error":first.get("message"),"after_amount":after["payments"]["paid_amount"]["value"],"final_ok":result.get("final_result",{}).get("ok")}))
