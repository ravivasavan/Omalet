#!/usr/bin/env python3
"""Grab one JPEG still from an Owlet Cam over TUTK P2P."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from ctypes import (
    CDLL,
    POINTER,
    Structure,
    byref,
    c_char,
    c_char_p,
    c_int,
    c_int32,
    c_uint,
    c_uint8,
    c_uint16,
    c_uint32,
    sizeof,
)
from pathlib import Path

HOME = Path.home()
STATE_DIR = HOME / ".local" / "state" / "omarchy"
SHARE_DIR = HOME / ".local" / "share" / "omarchy" / "owlet"
META_FILE = STATE_DIR / "owlet-camera.json"
SNAPSHOT_FILE = STATE_DIR / "owlet-camera.jpg"
LIB_FILE = SHARE_DIR / "lib" / "libIOTCAPIs_ALL.so"
KEY_FILE = SHARE_DIR / "tutk.key"


class St_IOTCConnectInput(Structure):
    _fields_ = [
        ("cb", c_uint32),
        ("authentication_type", c_uint32),
        ("auth_key", c_char * 8),
        ("timeout", c_uint32),
    ]


class AVClientStartInConfig(Structure):
    _fields_ = [
        ("cb", c_uint32),
        ("iotc_session_id", c_uint32),
        ("iotc_channel_id", c_uint8),
        ("timeout_sec", c_uint32),
        ("account_or_identity", c_char_p),
        ("password_or_token", c_char_p),
        ("resend", c_int32),
        ("security_mode", c_uint32),
        ("auth_type", c_uint32),
        ("sync_recv_data", c_int32),
    ]


class AVClientStartOutConfig(Structure):
    _fields_ = [
        ("cb", c_uint32),
        ("server_type", c_uint32),
        ("resend", c_int32),
        ("two_way_streaming", c_int32),
        ("sync_recv_data", c_int32),
        ("security_mode", c_uint32),
    ]


ERRORS = {
    -10: "TUTK license rejected",
    -13: "Camera P2P timed out",
    -19: "Camera not found on TUTK",
    -24: "Camera is not listening",
    -40: "TUTK permission denied",
    -42: "TUTK relay failed",
    -45: "Camera already has a viewer",
    -48: "Camera session limit reached",
}


def atomic_write_bytes(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.chmod(tmp, mode)
    tmp.replace(path)


def load_lib() -> CDLL:
    if not LIB_FILE.is_file():
        raise RuntimeError("TUTK library is not installed")
    return CDLL(str(LIB_FILE))


def license_key() -> str:
    return os.environ.get("OWLET_TUTK_KEY") or (
        KEY_FILE.read_text().strip() if KEY_FILE.is_file() else ""
    )


def connect(lib: CDLL, uid: str, auth_key: str, timeout: int = 18) -> int:
    key = license_key()
    if key:
        lib.TUTK_SDK_Set_License_Key.argtypes = [c_char_p]
        lib.TUTK_SDK_Set_License_Key.restype = c_int
        status = lib.TUTK_SDK_Set_License_Key(key.encode())
        if status < 0:
            raise RuntimeError(ERRORS.get(status, f"TUTK license error {status}"))
    if hasattr(lib, "TUTK_SDK_Set_Region"):
        lib.TUTK_SDK_Set_Region.argtypes = [c_int]
        lib.TUTK_SDK_Set_Region(3)
    lib.IOTC_Initialize2.argtypes = [c_uint16]
    lib.IOTC_Initialize2.restype = c_int
    init = lib.IOTC_Initialize2(c_uint16(0))
    if init not in (0, -3):
        raise RuntimeError(ERRORS.get(init, f"TUTK init error {init}"))
    lib.IOTC_Get_SessionID.restype = c_int
    sid = lib.IOTC_Get_SessionID()
    if sid < 0:
        raise RuntimeError(ERRORS.get(sid, f"TUTK session error {sid}"))
    cin = St_IOTCConnectInput()
    cin.cb = sizeof(cin)
    cin.authentication_type = 0
    cin.auth_key = auth_key.encode()[:8]
    cin.timeout = timeout
    lib.IOTC_Connect_ByUIDEx.argtypes = [c_char_p, c_int, POINTER(St_IOTCConnectInput)]
    lib.IOTC_Connect_ByUIDEx.restype = c_int
    ret = lib.IOTC_Connect_ByUIDEx(uid.encode(), sid, byref(cin))
    if ret < 0:
        raise RuntimeError(ERRORS.get(ret, f"TUTK connect error {ret}"))
    return ret


def start_av(lib: CDLL, session_id: int, password: str) -> int:
    lib.avInitialize.argtypes = [c_int]
    lib.avInitialize.restype = c_int
    lib.avInitialize(4)
    cfg_in = AVClientStartInConfig()
    cfg_out = AVClientStartOutConfig()
    cfg_in.cb = sizeof(cfg_in)
    cfg_out.cb = sizeof(cfg_out)
    cfg_in.iotc_session_id = session_id
    cfg_in.iotc_channel_id = 0
    cfg_in.timeout_sec = 12
    account = password.encode()
    secret = password.encode()
    cfg_in.account_or_identity = account
    cfg_in.password_or_token = secret
    cfg_in.resend = 1
    cfg_in.security_mode = 2
    lib.avClientStartEx.argtypes = [POINTER(AVClientStartInConfig), POINTER(AVClientStartOutConfig)]
    lib.avClientStartEx.restype = c_int
    av_id = lib.avClientStartEx(byref(cfg_in), byref(cfg_out))
    if av_id < 0:
        raise RuntimeError(ERRORS.get(av_id, f"TUTK AV error {av_id}"))
    return av_id


def recv_jpeg(lib: CDLL, av_id: int, timeout: float = 12.0) -> bytes:
    frame_buf = (c_char * (1024 * 1024))()
    info_buf = (c_char * 4096)()
    actual = c_int32(0)
    expected = c_int32(0)
    info_len = c_int32(0)
    index = c_uint32(0)
    lib.avRecvFrameData2.restype = c_int
    lib.avRecvFrameData2.argtypes = [
        c_int,
        POINTER(c_char),
        c_int,
        POINTER(c_int32),
        POINTER(c_int32),
        POINTER(c_char),
        c_int,
        POINTER(c_int32),
        POINTER(c_uint32),
    ]
    deadline = time.time() + timeout
    chunks: list[bytes] = []
    while time.time() < deadline:
        n = lib.avRecvFrameData2(
            av_id,
            frame_buf,
            1024 * 1024,
            byref(actual),
            byref(expected),
            info_buf,
            4096,
            byref(info_len),
            byref(index),
        )
        if n <= 0:
            time.sleep(0.02)
            continue
        data = bytes(frame_buf[:n])
        if data[:3] == b"\xff\xd8\xff":
            return data
        chunks.append(data)
        if len(chunks) >= 8:
            break
    if not chunks:
        raise RuntimeError("Camera sent no video frame")
    return ffmpeg_jpeg(b"".join(chunks))


def ffmpeg_jpeg(raw: bytes) -> bytes:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "h264", "-i", "pipe:0", "-frames:v", "1", "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"],
        input=raw,
        capture_output=True,
        timeout=8,
        check=False,
    )
    if proc.returncode != 0 or proc.stdout[:3] != b"\xff\xd8\xff":
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "hevc", "-i", "pipe:0", "-frames:v", "1", "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"],
            input=raw,
            capture_output=True,
            timeout=8,
            check=False,
        )
    if proc.returncode != 0 or proc.stdout[:3] != b"\xff\xd8\xff":
        raise RuntimeError("Could not decode camera frame")
    return proc.stdout


def grab() -> bytes:
    meta = json.loads(META_FILE.read_text()) if META_FILE.is_file() else {}
    uid = str(meta.get("tutkid") or "")
    auth_key = str(meta.get("authKey") or "")
    password = str(meta.get("password") or "")
    if not uid or not auth_key or not password:
        raise RuntimeError("Missing Owlet camera P2P credentials")
    lib = load_lib()
    sid = -1
    av_id = -1
    try:
        sid = connect(lib, uid, auth_key)
        av_id = start_av(lib, sid, password)
        return recv_jpeg(lib, av_id)
    finally:
        if av_id >= 0:
            lib.avClientStop(av_id)
            lib.avDeInitialize()
        if sid >= 0:
            lib.IOTC_Session_Close(sid)
        lib.IOTC_DeInitialize()


def main() -> int:
    try:
        jpeg = grab()
        atomic_write_bytes(SNAPSHOT_FILE, jpeg)
        print("ok", len(jpeg), file=sys.stderr)
        return 0
    except Exception as err:  # noqa: BLE001
        print(str(err) or "Camera still failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
