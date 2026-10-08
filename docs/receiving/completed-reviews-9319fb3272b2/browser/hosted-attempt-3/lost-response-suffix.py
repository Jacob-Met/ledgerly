
# Receiving-only injection: the real mock send succeeds before its response is lost.
_history_original_handle_json = handle_json
_history_lost_response_used = False
def handle_json(raw):
    global _history_lost_response_used
    request = json.loads(raw)
    if request.get("action") != "approve" or _history_lost_response_used:
        return _history_original_handle_json(raw)
    _history_lost_response_used = True
    original_send = SESSION.mock.send_invoice
    def send_then_lose_response(*args, **kwargs):
        original_send(*args, **kwargs)
        raise TimeoutError("Receiving-only lost response after the real mock send")
    SESSION.mock.send_invoice = send_then_lose_response
    try:
        return _history_original_handle_json(raw)
    finally:
        SESSION.mock.send_invoice = original_send
