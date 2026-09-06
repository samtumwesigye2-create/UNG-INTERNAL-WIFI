from pathlib import Path
import importlib.util
ROOT = Path(__file__).resolve().parents[1]
def installer():
    spec = importlib.util.spec_from_file_location("pi_installer", ROOT/"deploy/pi_installer.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
def test_safe_plan():
    assert "Apply firewall policy with Internet forwarding disabled" in installer().plan()
def test_service_restarts():
    text = (ROOT/"systemd/internal-wifi-api.service").read_text()
    assert "Restart=on-failure" in text
    assert "WantedBy=multi-user.target" in text
