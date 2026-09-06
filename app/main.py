from __future__ import annotations
import os, time
from fastapi import FastAPI, Header, HTTPException, Depends

STARTED = time.time()
ADMIN_TOKEN = os.environ.get("INTERNAL_WIFI_ADMIN_TOKEN", "")
app = FastAPI(title="Internal Wi-Fi Platform", version="0.5.0")

def require_admin(x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN:
        raise HTTPException(503, "Admin API disabled until INTERNAL_WIFI_ADMIN_TOKEN is configured")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token")

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.5.0"}

@app.get("/api/status")
def status():
    return {
        "status": "ok",
        "version": "0.5.0",
        "offline_first": True,
        "internet_enabled": False,
        "subnet": os.environ.get("INTERNAL_WIFI_SUBNET", "192.168.50.0/24"),
        "gateway": os.environ.get("INTERNAL_WIFI_GATEWAY", "192.168.50.1"),
        "dns_suffix": os.environ.get("INTERNAL_WIFI_DNS_SUFFIX", "internal"),
        "uptime_seconds": round(time.time() - STARTED, 1),
    }

@app.get("/api/admin/config")
def admin_config(_: None = Depends(require_admin)):
    return {
        "ssid": os.environ.get("INTERNAL_WIFI_SSID", "InternalNet"),
        "internet_enabled": False,
        "admin_api_secured": True,
    }
