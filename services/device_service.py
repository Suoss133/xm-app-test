# services/device_service.py
import subprocess
from typing import List, Dict


def list_devices() -> List[Dict]:
    try:
        r = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True, timeout=8, check=False
        )
        devices = []
        for line in r.stdout.strip().splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            udid, status = parts[0], parts[1]
            model = None
            for p in parts[2:]:
                if p.startswith("model:"):
                    model = p.split(":", 1)[1]
            devices.append({"udid": udid, "status": status, "model": model})
        return devices
    except Exception as e:
        return []


