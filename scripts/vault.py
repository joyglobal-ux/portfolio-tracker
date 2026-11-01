"""포트폴리오 데이터 금고 — data/*.json(평문, git에 안 올라감) <-> data/vault.json(암호문, 공개).

    python scripts/vault.py decrypt   # vault.json → data/*.json  (편집 전에 항상 먼저)
    python scripts/vault.py encrypt   # data/*.json → vault.json  (편집 후, 커밋 전)
    python scripts/vault.py check     # 비밀번호로 열리는지만 확인

비밀번호: 환경변수 VAULT_PASSWORD → 없으면 macOS 키체인(서비스명 polaris-vault).
  키체인 등록:  security add-generic-password -a polaris -s polaris-vault -w
암호: AES-256-GCM, 키 = PBKDF2-HMAC-SHA256(비밀번호, salt, 600,000회).
브라우저(index.html의 Web Crypto)도 같은 파라미터로 푼다 — 바꾸면 양쪽을 같이 바꿀 것.
salt는 비밀번호를 바꾸기 전까지 유지한다(브라우저에 기억된 키가 계속 맞도록). IV는 매번 새로.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
VAULT = os.path.join(DATA, "vault.json")
FILES = ["meta", "positions", "equity", "journal", "log", "watchlist"]
ITER = 600_000


def password() -> str:
    pw = os.environ.get("VAULT_PASSWORD")
    if pw:
        return pw
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", "polaris-vault", "-w"],
                             capture_output=True, text=True, check=True)
        return out.stdout.rstrip("\n")
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit("비밀번호 없음: VAULT_PASSWORD 환경변수나 키체인(polaris-vault)을 설정할 것.")


def derive(pw: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode("utf-8"))


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def unb64(s: str) -> bytes:
    return base64.b64decode(s)


def read_vault() -> dict:
    with open(VAULT, encoding="utf-8") as f:
        return json.load(f)


def open_vault(v: dict, pw: str) -> dict:
    key = derive(pw, unb64(v["salt"]))
    try:
        pt = AESGCM(key).decrypt(unb64(v["iv"]), unb64(v["ct"]), None)
    except Exception:
        sys.exit("복호화 실패 — 비밀번호가 다르거나 vault.json이 손상됐다.")
    return json.loads(pt.decode("utf-8"))


def cmd_decrypt() -> None:
    data = open_vault(read_vault(), password())
    for name in FILES:
        if name in data:
            with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(data[name], f, ensure_ascii=False, indent=2)
                f.write("\n")
    print(f"decrypted {len([n for n in FILES if n in data])} files → data/*.json (git 제외)")


def cmd_encrypt() -> None:
    pw = password()
    data = {}
    for name in FILES:
        p = os.path.join(DATA, name + ".json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                data[name] = json.load(f)
    salt = None
    if os.path.exists(VAULT):
        old = read_vault()
        prev = open_vault(old, pw)     # 다른 비밀번호로 덮어써서 기존 기기가 잠기는 사고 방지
        if prev == data:               # 내용이 같으면 그대로 둔다 (IV만 바뀐 무의미한 커밋 방지)
            print("unchanged — vault.json 유지")
            return
        salt = unb64(old["salt"])
    salt = salt or os.urandom(16)
    iv = os.urandom(12)
    ct = AESGCM(derive(pw, salt)).encrypt(iv, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), None)
    asof = (data.get("positions") or {}).get("asOf") or (data.get("meta") or {}).get("lastUpdated")
    with open(VAULT, "w", encoding="utf-8") as f:
        json.dump({"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": ITER,
                   "salt": b64(salt), "iv": b64(iv), "ct": b64(ct), "asOf": asof}, f)
        f.write("\n")
    print(f"encrypted {len(data)} files → data/vault.json (asOf {asof})")


def cmd_check() -> None:
    data = open_vault(read_vault(), password())
    print("ok:", ", ".join(sorted(data)))


if __name__ == "__main__":
    {"decrypt": cmd_decrypt, "encrypt": cmd_encrypt, "check": cmd_check}.get(
        (sys.argv[1:] or [""])[0], lambda: sys.exit(__doc__))()
