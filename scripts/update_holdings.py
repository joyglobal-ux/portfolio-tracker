"""구성종목 시트 CSV → positions.json의 숫자(비중·수익률) 갱신. 서사(thesis·손절·메모)는 보존.

필요: HOLDINGS_CSV_URL (구성종목 탭 게시 CSV).
원칙: 평가비중(%)·수익률(%)·종목명·코드만 추출. **원화 금액은 추출도 출력도 하지 않는다.**
기존 종목은 thesis/손절/메모 보존하고 숫자만 갱신, 신규 종목은 placeholder thesis로 추가,
시트에서 사라진(매도) 종목은 제거. 현금(KRW/USD)은 cashWeight로 합산.
"""
import csv
import datetime
import io
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POS = os.path.join(ROOT, "data", "positions.json")


def norm(h):
    return (h or "").replace(" ", "").replace("\n", "").strip()


def ppct(s):
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("%", "")
    if not s or "#" in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def cell(r, i):
    return r[i] if (i is not None and i < len(r)) else None


def main():
    url = os.environ.get("HOLDINGS_CSV_URL")
    if not url:
        print("HOLDINGS_CSV_URL 미설정 — 건너뜀 (수동 운영).")
        return

    raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))

    hidx = next((i for i, r in enumerate(rows) if any(norm(c) == "종목명" for c in r)), None)
    if hidx is None:
        raise SystemExit("헤더('종목명')를 못 찾음 — CSV 구조 확인 필요")
    H = rows[hidx]
    print("헤더:", [norm(h) for h in H if norm(h)])  # 칼럼명만 (원화 없음)

    def col(pred):
        for i, h in enumerate(H):
            if pred(norm(h)):
                return i
        return None

    c_code = col(lambda h: "코드" in h)
    c_name = col(lambda h: h == "종목명")
    c_ret = col(lambda h: h == "수익률")
    c_wt = col(lambda h: h == "평가비중")
    if c_name is None or c_wt is None:
        raise SystemExit("종목명/평가비중 칼럼을 못 찾음")

    sheet, cash = [], 0.0
    for r in rows[hidx + 1:]:
        name = (cell(r, c_name) or "").strip()
        if not name:
            continue
        wt = ppct(cell(r, c_wt))
        if wt is None:
            continue
        if "현금" in name:
            cash += wt
            continue
        if wt <= 0:  # 매도 완료/히스토리 행(평가비중 0) 제외 — 활성 보유만
            continue
        code = (cell(r, c_code) or "").strip()
        ret = ppct(cell(r, c_ret))
        credit = "신용" in name
        ticker = code + ("C" if credit else "")
        sheet.append({
            "ticker": ticker, "name": name,
            "weight": round(wt, 1),
            "ret": round(ret, 2) if ret is not None else None,
            "credit": credit,
        })

    if not sheet:
        raise SystemExit("보유종목 0건 — CSV 구조 확인 필요")

    with open(POS, encoding="utf-8") as f:
        pos = json.load(f)
    # 키 = 티커|종목명 — 같은 티커의 다중 계좌 행(예: 본주 vs "(2nd)")이 서로 덮어쓰지 않게.
    # (티커만 쓰면 000660 두 행이 한 객체로 합쳐져 본주가 증발하는 버그 — 2026-07-06 수정)
    existing = {f'{h["ticker"]}|{h["name"]}': h for h in pos.get("holdings", [])}

    merged = []
    for sh in sheet:
        key = f'{sh["ticker"]}|{sh["name"]}'
        if key in existing:
            h = existing[key]  # thesis/stop/note/tag/sector 보존
            h["weight"] = sh["weight"]
            h["ret"] = sh["ret"]
            h["credit"] = sh["credit"]
            merged.append(h)
        else:
            merged.append({
                "ticker": sh["ticker"], "name": sh["name"],
                "tag": "신규", "tagColor": "go", "sector": "",
                "weight": sh["weight"], "ret": sh["ret"], "credit": sh["credit"],
                "thesis": "(자동 추가 — thesis 입력 필요)", "stop": "", "note": "",
            })

    pos["holdings"] = merged
    pos["cashWeight"] = round(cash, 1)
    pos["creditWeight"] = round(sum(h["weight"] for h in merged if h.get("credit")), 1)
    pos["asOf"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    with open(POS, "w", encoding="utf-8") as f:
        json.dump(pos, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("갱신: {}종목 · 현금 {}% · 신용 {}% · asOf {}".format(
        len(merged), pos["cashWeight"], pos["creditWeight"], pos["asOf"]))
    for h in merged:
        print("  {}: 비중 {}% · 수익 {}%".format(h["name"], h["weight"], h["ret"]))


if __name__ == "__main__":
    main()
