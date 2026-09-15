#!/usr/bin/env python3
"""Poll Owlet Sock 3 vitals and write a state file for the bar widget."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pyowletapi.api import OwletAPI
from pyowletapi.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletCredentialsError,
    OwletDevicesError,
    OwletError,
)
from pyowletapi.sock import Sock

HOME = Path.home()
STATE_DIR = HOME / ".local" / "state" / "omarchy"
STATE_FILE = STATE_DIR / "owlet.json"
TOKEN_FILE = STATE_DIR / "owlet-tokens.json"
AUTH_FILE = STATE_DIR / "owlet-auth.json"
ALERT_FILE = STATE_DIR / "owlet-alerts.json"
SNAPSHOT_FILE = STATE_DIR / "owlet-camera.jpg"
CAMERA_META_FILE = STATE_DIR / "owlet-camera.json"
DEFAULT_EMAIL = ""
DEFAULT_REGION = "world"
CAMERA_FIREBASE_KEY = "AIzaSyCx17leGPCKu5tZ1BLPni5LbAAlVvnNxZQ"
CAMERA_DEVICES_URL = "https://devices-public.owletdata.com/v2"
CAMERA_DISCOVER_EVERY = 15 * 60
CAMERA_REDISCOVER_EMPTY = 60
SNAPSHOT_MAX_BYTES = 8 * 1024 * 1024

SLEEP_STATES = {0: "unknown", 1: "awake", 8: "light sleep", 15: "deep sleep"}

ALERT_SPECS = {
    "critical_oxygen_alert": {
        "urgency": "critical",
        "glyph": "󰩂",
        "headline": "Owlet oxygen",
        "body": "Critical oxygen alert",
        "skip_if_charging": False,
    },
    "low_oxygen_alert": {
        "urgency": "critical",
        "glyph": "󰩂",
        "headline": "Owlet oxygen",
        "body": "Low oxygen alert",
        "skip_if_charging": False,
    },
    "high_oxygen_alert": {
        "urgency": "critical",
        "glyph": "󰩂",
        "headline": "Owlet oxygen",
        "body": "High oxygen alert",
        "skip_if_charging": False,
    },
    "low_heart_rate_alert": {
        "urgency": "critical",
        "glyph": "󰓃",
        "headline": "Owlet heart rate",
        "body": "Low heart rate alert",
        "skip_if_charging": False,
    },
    "high_heart_rate_alert": {
        "urgency": "critical",
        "glyph": "󰓃",
        "headline": "Owlet heart rate",
        "body": "High heart rate alert",
        "skip_if_charging": False,
    },
    "critical_battery_alert": {
        "urgency": "critical",
        "glyph": "󰁺",
        "headline": "Owlet battery",
        "body": "Critical sock battery",
        "skip_if_charging": False,
    },
    "low_battery_alert": {
        "urgency": "normal",
        "glyph": "󰁻",
        "headline": "Owlet battery",
        "body": "Sock battery is low",
        "skip_if_charging": False,
    },
    "lost_power_alert": {
        "urgency": "normal",
        "glyph": "󰚥",
        "headline": "Owlet base station",
        "body": "Base station lost power",
        "skip_if_charging": False,
    },
    "sock_disconnected": {
        "urgency": "normal",
        "glyph": "󰂲",
        "headline": "Owlet sock",
        "body": "Sock disconnected from the base",
        "skip_if_charging": True,
    },
    "sock_off": {
        "urgency": "normal",
        "glyph": "󰁔",
        "headline": "Owlet sock",
        "body": "Sock is off",
        "skip_if_charging": True,
    },
}


def atomic_write(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    tmp.write_text(data + "\n")
    os.chmod(tmp, mode)
    tmp.replace(path)


def atomic_write_bytes(path: Path, payload: bytes, mode: int = 0o600) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.chmod(tmp, mode)
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text()
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def secret_password(email: str) -> str | None:
    try:
        result = subprocess.run(
            ["secret-tool", "lookup", "service", "owlet", "username", email],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    password = result.stdout.rstrip("\n")
    return password or None


def load_auth() -> tuple[str, str]:
    auth = read_json(AUTH_FILE)
    email = os.environ.get("OWLET_EMAIL") or str(auth.get("email") or DEFAULT_EMAIL)
    region = os.environ.get("OWLET_REGION") or str(auth.get("region") or DEFAULT_REGION)
    if region not in ("world", "europe"):
        region = DEFAULT_REGION
    return email.strip(), region


def load_tokens() -> dict[str, Any]:
    tokens = read_json(TOKEN_FILE)
    if not tokens:
        return {}
    expiry = tokens.get("expiry")
    try:
        tokens["expiry"] = float(expiry) if expiry is not None else None
    except (TypeError, ValueError):
        tokens["expiry"] = None
    return tokens


def save_tokens(tokens: dict[str, Any] | None) -> None:
    if not tokens:
        return
    atomic_write(
        TOKEN_FILE,
        {
            "api_token": tokens.get("api_token"),
            "expiry": tokens.get("expiry"),
            "refresh": tokens.get("refresh"),
        },
    )


def clear_secret(email: str) -> None:
    cmd = ["secret-tool", "clear", "service", "owlet"]
    if email:
        cmd.extend(["username", email])
    try:
        subprocess.run(cmd, check=False, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def logout() -> dict[str, Any]:
    email, _region = load_auth()
    clear_secret(email)
    for path in (TOKEN_FILE, ALERT_FILE, SNAPSHOT_FILE):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return empty_state(
        status="needs_login",
        needs_login=True,
        error="",
        label="Omalet",
        camera=empty_camera(),
    )


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def as_number(value: Any) -> float | None:
    if value is None or value is False:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def rounded(value: Any) -> int | None:
    number = as_number(value)
    if number is None:
        return None
    return int(round(number))


def skin_temperature_c(value: Any) -> float | None:
    number = as_number(value)
    if number is None:
        return None
    if number > 80:
        number = number / 10.0
    if number < 10 or number > 45:
        return None
    return round(number, 1)


def status_for(properties: dict[str, Any], connection_status: str) -> str:
    charging = as_bool(properties.get("charging"))
    sock_off = as_bool(properties.get("sock_off"))
    connected = as_bool(properties.get("sock_connection"))
    base_on = as_bool(properties.get("base_station_on"))
    if charging:
        return "charging"
    if sock_off:
        return "sock_off"
    if connection_status.lower() != "online" or not connected or not base_on:
        return "offline"
    return "monitoring"


HEART_ICON = "󰋑"  # nf-md-heart
AIR_ICON = "󰖝"  # nf-md-weather-windy


def bar_label(status: str, properties: dict[str, Any]) -> str:
    if status == "charging":
        battery = rounded(properties.get("battery_percentage"))
        return f"{battery}%" if battery is not None else "chg"
    if status == "sock_off":
        return "off"
    if status != "monitoring":
        return "Owlet"
    hr = rounded(properties.get("heart_rate"))
    ox = rounded(properties.get("oxygen_saturation"))
    if (hr is None or hr <= 0) and (ox is None or ox <= 0):
        return f"{HEART_ICON} …"
    hr_text = "—" if hr is None or hr <= 0 else str(hr)
    ox_text = "—" if ox is None or ox <= 0 else f"{ox}%"
    return f"{HEART_ICON} {hr_text}  {AIR_ICON} {ox_text}"


def pick_alerts(properties: dict[str, Any]) -> dict[str, bool]:
    return {key: as_bool(properties.get(key)) for key in ALERT_SPECS}


def rising_alerts(
    current: dict[str, bool],
    previous: dict[str, bool] | None,
    charging: bool,
) -> list[dict[str, str]]:
    if previous is None:
        return []
    fired: list[dict[str, str]] = []
    for key, spec in ALERT_SPECS.items():
        if spec["skip_if_charging"] and charging:
            continue
        if current.get(key) and not previous.get(key):
            fired.append(spec)
    return fired


def notify(spec: dict[str, str]) -> None:
    cmd = [
        "omarchy-notification-send",
        "--app-name",
        "Owlet",
        "-u",
        spec["urgency"],
        "-g",
        spec["glyph"],
        spec["headline"],
        spec["body"],
    ]
    try:
        subprocess.run(cmd, check=False, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        pass


def empty_camera(**overrides: Any) -> dict[str, Any]:
    camera = {
        "present": False,
        "id": "",
        "name": "",
        "status": "",
        "source": "",
        "snapshot_path": "",
        "error": "",
        "fetched_at": 0,
        "discovered_at": 0,
    }
    camera.update(overrides)
    return camera


def sanitize_camera(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return empty_camera()
    source = str(raw.get("source") or "")
    if source not in ("url", "owlet"):
        source = ""
    snapshot = str(raw.get("snapshot_path") or "")
    if ".." in snapshot or "owlet-camera.jpg" not in snapshot:
        snapshot = ""
    try:
        fetched_at = int(raw.get("fetched_at") or 0)
    except (TypeError, ValueError):
        fetched_at = 0
    try:
        discovered_at = int(raw.get("discovered_at") or 0)
    except (TypeError, ValueError):
        discovered_at = 0
    return empty_camera(
        present=raw.get("present") is True or bool(snapshot),
        id=str(raw.get("id") or "")[:40],
        name=str(raw.get("name") or "")[:40],
        status=str(raw.get("status") or "")[:24],
        source=source,
        snapshot_path=snapshot[:240],
        error=str(raw.get("error") or "")[:80],
        fetched_at=fetched_at,
        discovered_at=discovered_at,
    )


def previous_camera() -> dict[str, Any]:
    return sanitize_camera(read_json(STATE_FILE).get("camera"))


def empty_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "ok": False,
        "status": "error",
        "error": "",
        "needs_login": False,
        "fetched_at": int(time.time()),
        "label": "Owlet",
        "sock": {},
        "vitals": {},
        "alerts": {},
        "alert_count": 0,
        "camera": previous_camera(),
    }
    state.update(overrides)
    if not state.get("label"):
        state["label"] = "Owlet"
    if "camera" not in overrides:
        state["camera"] = previous_camera()
    return state


def write_state(state: dict[str, Any]) -> None:
    if "camera" not in state:
        state["camera"] = previous_camera()
    else:
        state["camera"] = sanitize_camera(state.get("camera"))
    atomic_write(STATE_FILE, state)


def snapshot_url_allowed(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def download_snapshot(url: str) -> bytes:
    if not snapshot_url_allowed(url) or len(url) > 500:
        raise ValueError("Camera URL must be http or https")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Omalet/1.1", "Accept": "image/jpeg,image/png,image/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            content_type = str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = response.read(SNAPSHOT_MAX_BYTES + 1)
    except urllib.error.HTTPError as err:
        raise ValueError("Camera still failed") from err
    except urllib.error.URLError as err:
        raise ValueError("Could not reach camera") from err
    except TimeoutError as err:
        raise ValueError("Camera still timed out") from err
    if len(data) > SNAPSHOT_MAX_BYTES:
        raise ValueError("Camera still is too large")
    jpeg = data[:3] == b"\xff\xd8\xff"
    png = data[:8] == b"\x89PNG\r\n\x1a\n"
    if not jpeg and not png:
        if content_type.startswith("image/"):
            raise ValueError("Camera still is not a JPEG")
        raise ValueError("Camera still is not an image")
    return data


def merge_state_camera(camera: dict[str, Any]) -> dict[str, Any]:
    state = read_json(STATE_FILE)
    if not state:
        state = empty_state(camera=camera)
    else:
        state["camera"] = camera
    write_state(state)
    return state


def should_discover_camera(camera: dict[str, Any]) -> bool:
    discovered_at = camera.get("discovered_at") or 0
    try:
        discovered_at = int(discovered_at)
    except (TypeError, ValueError):
        discovered_at = 0
    if discovered_at <= 0:
        return True
    age = time.time() - discovered_at
    if camera.get("present"):
        return age >= CAMERA_DISCOVER_EVERY
    return age >= CAMERA_REDISCOVER_EMPTY


def camera_identity(device: dict[str, Any]) -> str:
    ident = str(device.get("id") or "").strip()
    name = str(device.get("name") or "").strip()
    if ident:
        return ident
    if "/" in name:
        return name.rsplit("/", 1)[-1]
    return name


def is_owlet_camera_device(device: dict[str, Any]) -> bool:
    if not isinstance(device, dict):
        return False
    ident = camera_identity(device).upper()
    dtype = str(device.get("type") or device.get("deviceType") or "").lower()
    name = str(device.get("name") or "").lower()
    if "sock" in dtype or ident.startswith("AC000"):
        return False
    if "camera" in dtype:
        return True
    if ident.startswith(("OCA", "OCC", "OC0", "OC1", "OC2")):
        return True
    if "oca" in name or "occ" in name or "/oc" in name:
        return True
    return False


def camera_from_device(device: dict[str, Any]) -> dict[str, Any]:
    ident = camera_identity(device)
    label = str(
        device.get("displayName")
        or device.get("label")
        or device.get("name")
        or device.get("product_name")
        or ""
    )
    if not label or label.startswith("dsns/") or label.lower().startswith("owletcam-"):
        label = "Owlet Cam"
    return empty_camera(
        present=True,
        id=ident[:40],
        name=label[:40],
        status=str(device.get("status") or "online")[:24],
        source="owlet",
        discovered_at=int(time.time()),
    )


def load_camera_meta() -> dict[str, str]:
    data = read_json(CAMERA_META_FILE)
    return {
        "id": str(data.get("id") or "")[:40],
        "name": str(data.get("name") or "")[:40],
        "firmware": str(data.get("firmware") or "")[:24],
        "ip": str(data.get("ip") or "")[:40],
    }


def discover_lan_owlet_cam() -> dict[str, Any] | None:
    """Find an Owlet Cam by reverse-DNS of LAN neighbors (GL.iNet .lan names)."""
    try:
        result = subprocess.run(
            ["ip", "neigh", "show"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    import socket

    seen: set[str] = set()
    for line in result.stdout.splitlines():
        ip = line.split()[0] if line.split() else ""
        if ip.count(".") != 3 or ip in seen:
            continue
        seen.add(ip)
        try:
            host, _, _ = socket.gethostbyaddr(ip)
        except OSError:
            continue
        label = str(host).split(".")[0]
        if not label.lower().startswith("owletcam-"):
            continue
        ident = label.split("-", 1)[-1]
        if not ident:
            continue
        meta = load_camera_meta()
        name = meta["name"] if meta.get("id") == ident and meta.get("name") else "Owlet Cam"
        return camera_from_device({"id": ident, "name": name, "status": "online", "deviceType": "camera"})
    return None


async def discover_owlet_camera(email: str, password: str) -> dict[str, Any] | None:
    if not email or not password:
        return None
    try:
        import aiohttp
    except ImportError:
        return None
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword"
                f"?key={CAMERA_FIREBASE_KEY}",
                json={
                    "email": email,
                    "password": password,
                    "returnSecureToken": True,
                },
            ) as resp:
                if resp.status != 200:
                    return None
                auth = await resp.json()
            jwt = str(auth.get("idToken") or "")
            account_id = str(auth.get("localId") or "")
            if not jwt or not account_id:
                return None
            async with session.get(
                f"{CAMERA_DEVICES_URL}/accounts/{account_id}/devices",
                headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
    except Exception:  # noqa: BLE001 — discovery must never fail vitals
        return None

    devices = payload.get("devices") or payload.get("cameras") or payload
    if not isinstance(devices, list):
        return empty_camera(status="none", source="owlet", discovered_at=int(time.time()))
    for device in devices:
        if is_owlet_camera_device(device):
            return camera_from_device(device)
    return empty_camera(status="none", source="owlet", discovered_at=int(time.time()))


async def attach_discovered_camera(state: dict[str, Any], email: str) -> dict[str, Any]:
    camera = sanitize_camera(state.get("camera") or previous_camera())
    if SNAPSHOT_FILE.is_file() and not camera.get("snapshot_path"):
        camera["snapshot_path"] = str(SNAPSHOT_FILE)
        camera["present"] = True
    lan = discover_lan_owlet_cam()
    if lan:
        discovered = lan
    elif not should_discover_camera(camera):
        state["camera"] = camera
        return state
    else:
        password = secret_password(email) if email else None
        discovered = None
        if password:
            discovered = await discover_owlet_camera(email, password)
        if discovered is None:
            state["camera"] = camera
            return state
        if not discovered.get("present"):
            known = str(camera.get("id") or "").upper()
            if known.startswith(("OCC", "OCA")):
                discovered = camera
                discovered["discovered_at"] = int(time.time())
    if discovered.get("present"):
        if camera.get("snapshot_path"):
            discovered["snapshot_path"] = camera["snapshot_path"]
            discovered["fetched_at"] = camera.get("fetched_at") or 0
        if camera.get("error") and not discovered.get("error"):
            discovered["error"] = camera["error"]
        if camera.get("source") == "url":
            discovered["source"] = "url"
        if camera.get("name") and not discovered.get("name"):
            discovered["name"] = camera["name"]
    state["camera"] = discovered
    return state


def camera_from_snapshot(error: str = "") -> dict[str, Any]:
    camera = previous_camera()
    now = int(time.time())
    if error:
        camera["error"] = error[:80]
        camera["source"] = camera.get("source") or "url"
        return camera
    camera.update(
        {
            "present": True,
            "source": "url" if camera.get("source") != "owlet" else camera.get("source") or "url",
            "snapshot_path": str(SNAPSHOT_FILE),
            "error": "",
            "fetched_at": now,
            "status": camera.get("status") or "online",
            "name": camera.get("name") or "Camera",
        }
    )
    return camera


def build_vitals(properties: dict[str, Any]) -> dict[str, Any]:
    sleep_raw = rounded(properties.get("sleep_state"))
    return {
        "heart_rate": rounded(properties.get("heart_rate")),
        "oxygen_saturation": rounded(properties.get("oxygen_saturation")),
        "oxygen_10_av": rounded(properties.get("oxygen_10_av")),
        "battery_percentage": rounded(properties.get("battery_percentage")),
        "battery_minutes": rounded(properties.get("battery_minutes")),
        "signal_strength": rounded(properties.get("signal_strength")),
        "skin_temperature_c": skin_temperature_c(properties.get("skin_temperature")),
        "sleep_state": sleep_raw,
        "sleep_label": SLEEP_STATES.get(sleep_raw if sleep_raw is not None else 0, "unknown"),
        "movement": as_bool(properties.get("movement")),
        "charging": as_bool(properties.get("charging")),
        "base_station_on": as_bool(properties.get("base_station_on")),
        "sock_connection": as_bool(properties.get("sock_connection")),
        "sock_off": as_bool(properties.get("sock_off")),
        "last_updated": str(properties.get("last_updated") or ""),
    }


async def poll() -> dict[str, Any]:
    email, region = load_auth()
    tokens = load_tokens()
    password = None
    if not email and not tokens.get("api_token"):
        return empty_state(
            status="needs_login",
            needs_login=True,
            error="Sign in to Owlet to show sock vitals",
        )
    api = OwletAPI(
        region,
        user=email,
        password=None,
        token=tokens.get("api_token"),
        expiry=tokens.get("expiry"),
        refresh=tokens.get("refresh"),
    )
    try:
        try:
            new_tokens = await api.authenticate()
        except (OwletAuthenticationError, OwletCredentialsError):
            password = secret_password(email)
            if not password:
                return empty_state(
                    status="needs_login",
                    needs_login=True,
                    error="Sign in to Owlet to show sock vitals",
                )
            await api.close()
            api = OwletAPI(region, user=email, password=password)
            try:
                new_tokens = await api.authenticate()
            except OwletCredentialsError:
                return empty_state(
                    status="needs_login",
                    needs_login=True,
                    error="Owlet login failed — check the password",
                )
            except OwletAuthenticationError as err:
                message = str(err)
                if "Too many" in message:
                    return empty_state(error="Owlet locked out — try again later")
                return empty_state(
                    status="needs_login",
                    needs_login=True,
                    error=message or "Owlet authentication failed",
                )

        if new_tokens:
            save_tokens(new_tokens)
        elif api.tokens.get("refresh"):
            save_tokens(api.tokens)

        devices = await api.get_devices(versions=[3, 2])
        socks = [
            Sock(api, device["device"])
            for device in devices["response"]
            if "device" in device
        ]
        if not socks:
            return empty_state(error="No Owlet sock found on this account")

        sock = socks[0]
        update = await sock.update_properties()
        if "tokens" in update:
            save_tokens(update["tokens"])
        properties = update.get("properties") or {}
        alerts = pick_alerts(properties)
        charging = as_bool(properties.get("charging"))
        previous = read_json(ALERT_FILE)
        previous_alerts = previous.get("alerts") if previous else None
        if not isinstance(previous_alerts, dict):
            previous_alerts = None
        for spec in rising_alerts(alerts, previous_alerts, charging):
            notify(spec)
        atomic_write(ALERT_FILE, {"alerts": alerts})

        status = status_for(properties, sock.connection_status)
        vitals = build_vitals(properties)
        active_alerts = [key for key, on in alerts.items() if on]
        state = {
            "ok": True,
            "status": status,
            "error": "",
            "needs_login": False,
            "fetched_at": int(time.time()),
            "label": bar_label(status, properties),
            "sock": {
                "name": sock.name,
                "serial": sock.serial,
                "connection_status": sock.connection_status,
                "version": sock.version,
            },
            "vitals": vitals,
            "alerts": alerts,
            "alert_names": active_alerts,
            "alert_count": len(active_alerts),
        }
        return await attach_discovered_camera(state, email)
    finally:
        await api.close()


def grab_native_still() -> bytes:
    from tutk_snapshot import grab

    return grab()


async def camera_poll() -> dict[str, Any]:
    url = sys.stdin.read().split("\n", 1)[0].strip()
    try:
        if url:
            data = await asyncio.to_thread(download_snapshot, url)
        else:
            data = await asyncio.to_thread(grab_native_still)
        atomic_write_bytes(SNAPSHOT_FILE, data)
        return merge_state_camera(camera_from_snapshot())
    except ValueError as err:
        return merge_state_camera(camera_from_snapshot(str(err) or "Camera still failed"))
    except Exception as err:  # noqa: BLE001 — fail closed into the widget
        message = str(err) or "Camera still failed"
        return merge_state_camera(camera_from_snapshot(message[:80]))


async def main() -> int:
    if "--logout" in sys.argv:
        state = logout()
        write_state(state)
        return 0

    if "--camera" in sys.argv:
        try:
            state = await asyncio.wait_for(camera_poll(), timeout=40)
        except asyncio.TimeoutError:
            state = merge_state_camera(camera_from_snapshot("Camera still timed out"))
        camera = state.get("camera") if isinstance(state.get("camera"), dict) else {}
        return 0 if state and not camera.get("error") else 1

    try:
        state = await asyncio.wait_for(poll(), timeout=25)
    except OwletCredentialsError:
        state = empty_state(
            status="needs_login",
            needs_login=True,
            error="Owlet login failed — check the password",
        )
    except OwletDevicesError:
        state = empty_state(error="No Owlet sock found on this account")
    except OwletConnectionError:
        state = empty_state(error="Could not reach Owlet")
    except asyncio.TimeoutError:
        state = empty_state(error="Owlet request timed out")
    except OwletError as err:
        state = empty_state(error=str(err) or "Owlet error")
    except Exception as err:  # noqa: BLE001 — fail closed into the widget
        state = empty_state(error="Owlet helper failed")
        print(f"owlet fetch failed: {err}", file=sys.stderr)

    write_state(state)
    if state.get("ok"):
        return 0
    if state.get("needs_login"):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
