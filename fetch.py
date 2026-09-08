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
DEFAULT_EMAIL = ""
DEFAULT_REGION = "world"

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
    }
    state.update(overrides)
    if not state.get("label"):
        state["label"] = "Owlet"
    return state


def write_state(state: dict[str, Any]) -> None:
    atomic_write(STATE_FILE, state)


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
        return {
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
    finally:
        await api.close()


async def main() -> int:
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
