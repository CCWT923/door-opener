import hashlib
import hmac
import json
import socket
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings

app = FastAPI(title="Door Opener IP门禁远程解锁", root_path="/door-opener/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_KEY = settings.SECRET_KEY
api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)

ADMIN_PASSWORD = settings.ADMIN_PASSWORD  # 设置登录密码
SECRET_KEY = _KEY.encode("utf-8")  # 用于签署 Session 的密钥

# Session 有效期
SESSION_EXPIRE_SECONDS = 3 * 24 * 3600


def load_doors_config() -> dict:
    config_file = Path("doors_config.json")
    if not config_file.exists():
        raise FileNotFoundError("未找到门禁配置文件：doors_config.json")

    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def create_session_token() -> str:
    """生成带签名的 Session Token: [exp_timestamp].[signature]"""
    expire_at = int(time.time()) + SESSION_EXPIRE_SECONDS
    data_to_sign = f"{expire_at}".encode()
    sig = hmac.new(SECRET_KEY, data_to_sign, hashlib.sha256).hexdigest()
    return f"{expire_at}.{sig}"


def verify_session(x_session_token: str | None = Header(None, alias="X-Session-Token")):
    """验证 Session 是否有效且未过期"""
    if not x_session_token or "." not in x_session_token:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        expire_str, sig = x_session_token.split(".", 1)
        expire_at = int(expire_str)

        # 1. 检查是否过期
        if time.time() > expire_at:
            raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

        # 2. 检查签名（防伪造，防止用户自己改 expire_str）
        expected_sig = hmac.new(
            SECRET_KEY, expire_str.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise HTTPException(status_code=401, detail="无效的 Session Token")

        return True
    except Exception:
        raise HTTPException(status_code=401, detail="身份认证失败")


def verify_dynamic_token(api_key: str = Security(api_key_header)):
    """
    基于时间窗的动态 HMAC-SHA256 校验 (防重放、防时序攻击)
    允许 1 分钟的时间误差（兼容前后端时钟微小不同步）
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Token")

    current_time = int(time.time())

    # 校验当前分钟及前后 1 分钟（共 3 分钟窗口）
    valid_tokens = []
    for offset in [-60, 0, 60]:
        time_block = str((current_time + offset) // 60).encode("utf-8")
        expected_hash = hmac.new(SECRET_KEY, time_block, hashlib.sha256).hexdigest()
        valid_tokens.append(expected_hash)

    # 安全地逐字节比较（防时序攻击）
    is_valid = any(hmac.compare_digest(api_key, token) for token in valid_tokens)

    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid or Expired API Token")

    return api_key


DOORS_CONFIG = load_doors_config()


def check_door_online(ip: str, port: int = 8000, timeout: float = 1.0) -> bool:
    """尝试与门禁建立 TCP 握手，检测是否在线"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False


def calculate_checksum(data: bytes) -> int:
    """
    计算门禁协议的校验和 (Checksum)
    大多数门禁设备使用：Sum(bytes) % 256 或 XOR(bytes)
    这里以标准的 8-bit 累加和模 256 为例
    """
    return sum(data) % 256


def generate_unlock_payload(sn_str: str, door_no: int = 1) -> bytes:
    # 帧头
    header = b"\x7e"

    # 门禁 SN 码 (ASCII 字节)
    sn_bytes = sn_str.encode("ascii")

    # 固定分隔符
    delimiter = b"\xff\xff\xff\xff"

    # 随机数/流水号 (若无握手要求，可固定或取当前时间戳)
    # 这里暂用抓包提取的有效 Session，如果是纯静态校验，可以保留固定 4 字节
    session_id = bytes.fromhex("10E2695E")

    # 开锁指令体 (根据门号 door_no 动态调整)
    # 03 03 00 00 00 00 04 [door_no] 00 00 00
    command = bytes(
        [0x03, 0x03, 0x00, 0x00, 0x00, 0x00, 0x04, door_no, 0x00, 0x00, 0x00]
    )

    # 待校验的数据段 (不包含 7E 帧头帧尾)
    body = sn_bytes + delimiter + session_id + command

    # 计算 Checksum
    chk = calculate_checksum(body)
    checksum_byte = bytes([chk])

    # 帧尾
    tail = b"\x7e"

    # 拼接完整的 Payload
    return header + body + checksum_byte + tail


# ----------------- API 路由层 -----------------


class LoginReq(BaseModel):
    password: str


@app.post("/login")
def login(req: LoginReq):
    # 使用 compare_digest 防止时序攻击爆破密码
    if not hmac.compare_digest(req.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=400, detail="密码错误！")

    token = create_session_token()
    return {"status": "success", "token": token, "message": "登录成功！"}


# 获取所有门禁列表（方便手机端下拉选择）
@app.get("/doors")
def get_doors_list(token: str = Depends(verify_session)):
    doors = []
    for id, info in DOORS_CONFIG.items():
        doors.append(
            {"id": id, "name": info["name"], "ip": info["ip"], "sn": info["sn"]}
        )
    return doors


@app.get("/doors/status")
def get_door_status(token: str = Depends(verify_session)):
    status_map = {}
    for door_id, door in DOORS_CONFIG.items():
        # TCP 端口探测，设置 0.8s 短超时
        is_online = check_door_online(door["ip"], door["port"], timeout=0.8)
        status_map[door_id] = "online" if is_online else "offline"
    return status_map


# 开锁接口
@app.post("/unlock/{door_id}")
def unlock_door(door_id: str, token: str = Depends(verify_session)):
    if door_id not in DOORS_CONFIG:
        raise HTTPException(
            status_code=404, detail=f"未找到 ID 为 '{door_id}' 的门禁配置"
        )

    door = DOORS_CONFIG[door_id]

    # 动态生成开锁 Hex 字节流
    payload = generate_unlock_payload(door["sn"], door["door_no"])

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(3.0)
        client.connect((door["ip"], door["port"]))
        client.sendall(payload)

        response = client.recv(1024)
        client.close()

        resp_hex = response.hex().upper()

        # 2101 代表开锁成功
        if "2101" in resp_hex or "2101" in resp_hex.replace(" ", ""):
            return {
                "status": "success",
                "message": f"【{door['name']}】开锁成功！🎉",
                "door_id": door_id,
                "sent_hex": payload.hex().upper(),
            }
        else:
            return {
                "status": "warning",
                "message": f"【{door['name']}】指令已发送，但设备返回异常状态: {resp_hex}",
                "sent_hex": payload.hex().upper(),
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"无法连接到【{door['name']}】({door['ip']}): {e!s}"
        )


@app.get("/health")
def health_check():
    return {"status": "ok"}


# 把当前目录挂载为静态文件目录，html=True 表示访问 / 自动找 index.html
app.mount("/", StaticFiles(directory="web", html=True), name="web")
