import os
from pathlib import Path
import importlib.util
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ["INTERNAL_WIFI_ADMIN_TOKEN"] = "x"*32
spec = importlib.util.spec_from_file_location("wifi_app", ROOT/"app/main.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
client = TestClient(mod.app)

def test_status_offline_first():
    r = client.get('/api/status'); assert r.status_code == 200
    assert r.json()['internet_enabled'] is False
    assert r.json()['offline_first'] is True

def test_admin_rejects_bad_token():
    assert client.get('/api/admin/config', headers={'x-admin-token':'wrong'}).status_code == 401

def test_admin_accepts_token():
    assert client.get('/api/admin/config', headers={'x-admin-token':'x'*32}).status_code == 200
