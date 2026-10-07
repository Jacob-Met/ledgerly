import argparse,json
from datetime import date,timedelta
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT/'dist'),**k)
    def log_message(self,*a):pass
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--chrome',default=r'C:\Program Files\Google\Chrome\Application\chrome.exe');args=ap.parse_args()
    out=ROOT/'public'/'captures';out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Quiet);Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_address[1]}/';errors=[];bad=[];external=[]
    try:
        assert urlopen(url,timeout=5).status==200
        with sync_playwright() as pw:
            options={'headless':True,'args':['--disable-gpu']}
            if args.chrome:options['executable_path']=args.chrome
            browser=pw.chromium.launch(**options);page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
            page.on('response',lambda r:bad.append((r.status,r.url)) if r.status>=400 else None);page.on('request',lambda r:external.append(r.url) if not r.url.startswith(url) else None)
            page.on('dialog',lambda d:d.accept());page.goto(url,wait_until='domcontentloaded');assert 'Ledgerly' in page.title()
            page.locator('#engine-start').click();page.wait_for_function("document.querySelector('#engine-status').textContent.includes('READY')",timeout=120000)
            page.locator('#load-fixture').click();page.wait_for_timeout(500);fixture_text=page.locator('#job-email').input_value();assert 'From:' in fixture_text
            page.locator('#analyze').click();page.wait_for_function("document.querySelector('#analysis').textContent.includes('confidence')")
            confidence=float(page.locator('#analysis .analysis-head strong').inner_text().split('%')[0]);assert confidence>=50
            page.locator('#draft').click();page.wait_for_function("document.querySelector('#approval-list').textContent.includes('SEND INVOICE')")
            gate='Gate verified' in page.locator('#status-message').inner_text();assert gate
            page.locator('#approval-list button[data-approve]').first.click();page.wait_for_function("document.querySelector('#ledger-list').textContent.includes('SENT')")
            page.locator('#payment-amount').fill('100');page.locator('#ledger-list button[data-pay]').click();page.wait_for_function("document.querySelector('#ledger-list').textContent.includes('PARTIALLY_PAID')")
            page.locator('#replay-webhook').click();page.wait_for_function("document.querySelector('#status-message').textContent.includes('Duplicate webhook')")
            due=page.locator('#ledger-list .invoice-card').get_attribute('data-due');overdue=(date.fromisoformat(due)+timedelta(days=1)).isoformat()
            page.locator('#demo-date').fill(overdue);page.locator('#advance-clock').click();page.locator('#run-chase').click();page.wait_for_function("document.querySelector('#approval-list').textContent.includes('SEND REMINDER')")
            page.screenshot(path=str(out/'ledgerly-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth');assert not overflow,'mobile horizontal overflow'
            page.screenshot(path=str(out/'ledgerly-mobile.png'),full_page=True)
            assert page.locator('#external-calls').inner_text()=='0';assert page.evaluate('localStorage.length')==0
            page.locator('#approval-list button[data-approve]').click();page.wait_for_function("document.querySelector('#ledger-list').textContent.includes('REMINDERS 1')")
            assert not errors,errors;assert not bad,bad;assert not external,external
            print(json.dumps({'engine':'Pyodide + actual Ledgerly Python modules','confidence':confidence,'gate_blocked_before_approval':gate,'payment_status':'PARTIALLY_PAID','duplicate_webhook_ignored':True,'overdue_reminder_approved':True,'external_requests':external,'mobile_overflow':overflow,'console_errors':errors,'http_errors':bad,'captures':[(p.name,p.stat().st_size) for p in out.glob('ledgerly-*.png')]}));browser.close()
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
