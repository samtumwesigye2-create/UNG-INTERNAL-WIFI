#!/usr/bin/env python3
import json, urllib.request
with urllib.request.urlopen("http://192.168.50.1:8080/api/status", timeout=3) as r:
    data = json.load(r)
assert data["offline_first"] is True
assert data["internet_enabled"] is False
print("OK: API healthy; Internet access disabled.")
