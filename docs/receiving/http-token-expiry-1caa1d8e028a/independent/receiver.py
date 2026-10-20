#!/usr/bin/env python3
"""Independent original-first HTTP token lifetime receiving; no real network."""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib
import io
import json
import math
import os
from pathlib import Path
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from unittest.mock import patch

BASE = 'https://ledgerly-receiver.invalid'
CID = 'fictional-receiving-client'
SECRET = 'fictional-receiving-secret'
INPUTS = ('ledgerly/__init__.py', 'ledgerly/extract.py', 'ledgerly/paypal.py')


def identity(path):
    b = path.read_bytes()
    s = path.stat()
    return {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
            'mtime_ns': s.st_mtime_ns, 'mode': s.st_mode, 'inode': s.st_ino}


class Clock:
    now = 1000.0


class MemoryResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload, allow_nan=True).encode())
        self.status = status


class Gateway:
    def __init__(self, clock, plans, *, enforce_expiry=False, invoice_error=False):
        self.clock, self.plans = clock, list(plans)
        self.enforce_expiry, self.invoice_error = enforce_expiry, invoice_error
        self.events, self.responses, self.tokens = [], [], {}
        self.failures = []

    def __call__(self, req, timeout=None, **kwargs):
        if kwargs:
            raise AssertionError('Unexpected transport kwargs')
        method, url = req.get_method(), req.full_url
        if not url.startswith(BASE + '/'):
            raise AssertionError('Unexpected URL; live transport is unavailable')
        path = url[len(BASE):]
        headers = {k.lower(): v for k, v in req.header_items()}
        event = {'method': method, 'path': path, 'clock': self.clock.now,
                 'timeout': timeout, 'body': None if req.data is None else req.data.decode()}
        self.events.append(event)
        if path == '/v1/oauth2/token':
            event['kind'] = 'oauth'
            expected_basic = 'Basic ' + base64.b64encode(f'{CID}:{SECRET}'.encode()).decode()
            event['shape_ok'] = (method == 'POST' and timeout == 20
                and req.data == b'grant_type=client_credentials'
                and headers.get('authorization') == expected_basic
                and headers.get('content-type') == 'application/x-www-form-urlencoded')
            if not self.plans:
                raise AssertionError('Unexpected extra token request')
            plan = self.plans.pop(0)
            started = self.clock.now
            self.clock.now += plan.get('latency', 0)
            if plan.get('error'):
                error = urllib.error.HTTPError(url, 503, 'fictional token service unavailable', {},
                    io.BytesIO(b'{"name":"FICTIONAL_AUTH_UNAVAILABLE"}'))
                self.failures.append(error)
                event['result'] = 'HTTP503'
                raise error
            payload = plan['payload']
            event['payload'] = payload
            event['completed_at'] = self.clock.now
            if isinstance(payload, dict):
                token, ttl = payload.get('access_token'), payload.get('expires_in')
                if isinstance(token, str) and token and type(ttl) in (int, float) and math.isfinite(ttl) and ttl > 0:
                    self.tokens[token] = started + ttl
            response = MemoryResponse(payload)
        else:
            event['kind'] = 'invoice'
            token = headers.get('authorization', '').removeprefix('Bearer ')
            event['token'] = token  # Only authored fictional token strings exist in this process.
            event['shape_ok'] = timeout == 30 and headers.get('content-type') == 'application/json'
            if self.invoice_error or (self.enforce_expiry and self.clock.now >= self.tokens.get(token, -math.inf)):
                status = 503 if self.invoice_error else 401
                event['result'] = f'HTTP{status}'
                raise urllib.error.HTTPError(url, status, 'fictional invoice refusal', {},
                    io.BytesIO(json.dumps({'name': 'FICTIONAL_REFUSAL', 'message': 'receiver control'}).encode()))
            response = MemoryResponse({'id': 'FICTIONAL-INVOICE', 'status': 'DRAFT'})
            event['result'] = 'HTTP200'
        self.responses.append(response)
        return response

    def kinds(self):
        return [x['kind'] for x in self.events]

    def all_shapes_ok(self):
        return all(x.get('shape_ok', False) for x in self.events)


def attempt(fn):
    try:
        value = fn()
    except Exception as error:
        return {'returned': False, 'exception': type(error).__name__, 'message': str(error),
                'http_status': getattr(error, 'http_status', getattr(error, 'code', None))}, error
    return {'returned': True, 'status': value.status, 'body': value.body}, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    if out.exists():
        parser.error('--out must be a new directory')
    before = {p: identity(source / p) for p in INPUTS}
    if out == source or source in out.parents or out in source.parents:
        parser.error('source and output must be disjoint')
    out.mkdir(parents=True)
    clock = Clock()
    checks = []

    def record(name, ok, gateway=None, **details):
        if gateway is not None:
            details['events'] = gateway.events
            details['returned_response_contexts_closed'] = all(r.closed for r in gateway.responses)
            details['request_shapes_ok'] = gateway.all_shapes_ok()
            ok = ok and details['returned_response_contexts_closed'] and details['request_shapes_ok']
        checks.append({'name': name, 'pass': bool(ok), **details})

    with patch('time.monotonic', lambda: clock.now), patch('socket.create_connection', side_effect=AssertionError('No network permitted')):
        sys.path.insert(0, str(source))
        paypal = importlib.import_module('ledgerly.paypal')
        if Path(paypal.__file__).resolve() != source / 'ledgerly/paypal.py':
            raise RuntimeError('Imported source mismatch')

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('LEDGERLY_ALLOW_NETWORK', None)
            try:
                paypal.HttpPayPalClient(CID, SECRET, BASE)
            except RuntimeError:
                gate_ok = True
            else:
                gate_ok = False
        record('constructor_network_gate_remains_required', gate_ok)

        def client():
            return paypal.HttpPayPalClient(CID, SECRET, BASE)

        with patch.dict(os.environ, {'LEDGERLY_ALLOW_NETWORK': '1'}, clear=False):
            clock.now = 1000.0
            peer = Gateway(clock, [
                {'payload': {'access_token': 'fictional-token-one', 'expires_in': 12}, 'latency': 3},
                {'payload': {'access_token': 'fictional-token-two', 'expires_in': 20}}], enforce_expiry=True)
            with patch('urllib.request.urlopen', peer):
                c = client()
                first, _ = attempt(lambda: c.get_invoice('FICTIONAL-FIRST'))
                clock.now = 1011.999
                second, _ = attempt(lambda: c.get_invoice('FICTIONAL-SECOND'))
                clock.now = 1012.0
                third, _ = attempt(lambda: c.get_invoice('FICTIONAL-THIRD'))
            invoice_tokens = [x['token'] for x in peer.events if x['kind'] == 'invoice']
            record('reuse_until_request_start_deadline_then_refresh_at_exact_expiry',
                all(x['returned'] for x in [first, second, third])
                and peer.kinds() == ['oauth', 'invoice', 'invoice', 'oauth', 'invoice']
                and invoice_tokens == ['fictional-token-one', 'fictional-token-one', 'fictional-token-two'],
                peer, operations=[first, second, third])

            clock.now = 2000.0
            peer = Gateway(clock, [{'payload': {'access_token': 'fictional-too-late', 'expires_in': 7}, 'latency': 7}], enforce_expiry=True)
            with patch('urllib.request.urlopen', peer):
                outcome, _ = attempt(lambda: client().get_invoice('FICTIONAL-LATENCY'))
            record('token_expired_during_response_is_refused_before_invoice',
                not outcome['returned'] and peer.kinds() == ['oauth'], peer, outcome=outcome)

            invalid_payloads = [
                ('missing_lifetime', {'access_token': 'fictional-invalid'}),
                ('zero_lifetime', {'access_token': 'fictional-invalid', 'expires_in': 0}),
                ('negative_lifetime', {'access_token': 'fictional-invalid', 'expires_in': -8}),
                ('boolean_lifetime', {'access_token': 'fictional-invalid', 'expires_in': True}),
                ('unreadable_lifetime', {'access_token': 'fictional-invalid', 'expires_in': 'twelve'}),
                ('nonfinite_lifetime', {'access_token': 'fictional-invalid', 'expires_in': float('inf')}),
                ('empty_access_token', {'access_token': '', 'expires_in': 10}),
                ('nonobject_response', [])]
            for name, payload in invalid_payloads:
                clock.now = 3000.0
                peer = Gateway(clock, [{'payload': payload},
                    {'payload': {'access_token': 'fictional-recovered', 'expires_in': 10}}])
                with patch('urllib.request.urlopen', peer):
                    c = client()
                    refused, _ = attempt(lambda: c.get_invoice('FICTIONAL-INVALID'))
                    next_call, _ = attempt(lambda: c.get_invoice('FICTIONAL-RECOVERED'))
                record('invalid_response_' + name,
                    not refused['returned'] and next_call['returned']
                    and peer.kinds() == ['oauth', 'oauth', 'invoice']
                    and peer.events[-1].get('token') == 'fictional-recovered', peer,
                    invalid_call=refused, separate_next_call=next_call)

            clock.now = 4000.0
            peer = Gateway(clock, [
                {'payload': {'access_token': 'fictional-before-failure', 'expires_in': 5}},
                {'error': True},
                {'payload': {'access_token': 'fictional-after-failure', 'expires_in': 10}}], enforce_expiry=True)
            with patch('urllib.request.urlopen', peer):
                c = client()
                first, _ = attempt(lambda: c.get_invoice('FICTIONAL-BEFORE-FAILURE'))
                clock.now = 4005.0
                failed, error = attempt(lambda: c.get_invoice('FICTIONAL-FAILED-REFRESH'))
                calls_at_failure = peer.kinds().copy()
                identical_error = bool(peer.failures) and error is peer.failures[-1]
                clock.now = 4006.0
                recovered, _ = attempt(lambda: c.get_invoice('FICTIONAL-NEXT-REQUEST'))
            record('failed_refresh_propagates_without_stale_fallback_or_replay',
                first['returned'] and not failed['returned'] and identical_error and recovered['returned']
                and calls_at_failure == ['oauth', 'invoice', 'oauth']
                and peer.kinds() == ['oauth', 'invoice', 'oauth', 'oauth', 'invoice'], peer,
                operations=[first, failed, recovered], same_exception_object=identical_error,
                events_at_refresh_failure=calls_at_failure)

            clock.now = 5000.0
            peer = Gateway(clock, [{'payload': {'access_token': 'fictional-post-control', 'expires_in': 15}}], invoice_error=True)
            body = {'detail': {'reference': 'FICTIONAL-DRAFT-CONTROL'}}
            with patch('urllib.request.urlopen', peer):
                outcome, _ = attempt(lambda: client().create_draft_invoice(body, prefer_representation=True))
            invoices = [e for e in peer.events if e['kind'] == 'invoice']
            record('invoice_failure_is_not_automatically_replayed',
                not outcome['returned'] and outcome['http_status'] == 503
                and peer.kinds() == ['oauth', 'invoice'] and len(invoices) == 1
                and invoices[0]['method'] == 'POST'
                and json.loads(invoices[0]['body']) == body, peer, outcome=outcome)

    after = {p: identity(source / p) for p in INPUTS}
    source_ok = before == after
    receipt = {'receiver': identity(Path(__file__).resolve()), 'source': str(source),
        'source_before': before, 'source_after': after, 'source_bytes_mtime_mode_inode_unchanged': source_ok,
        'environment': {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform()},
        'scope': 'Actual public HttpPayPalClient methods with authored in-memory urlopen and monotonic clock. No socket, real credential, provider account, persisted invoice or native installation was used.',
        'checks': checks, 'passed': sum(c['pass'] for c in checks), 'total': len(checks),
        'pass': source_ok and all(c['pass'] for c in checks)}
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=True) + '\n')
    print(json.dumps({'receipt': str(out / 'receipt.json'), 'passed': receipt['passed'], 'total': receipt['total'],
        'source_unchanged': source_ok, 'pass': receipt['pass'], 'failed': [c['name'] for c in checks if not c['pass']]}))
    return 0 if receipt['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
