"""자산관리 시트 CSV를 pull해서 data/equity.json·meta.json(숫자 필드)을 갱신.

필요: SHEET_CSV_URL 환경변수(GitHub Secret) = 자산관리 탭 게시 CSV.

원칙:
- 규모 지수 = 평가액 / BASE * 100  (BASE = 첫 데이터 행 평가액 = 100)
- 성과 지수(twr) = 누적 수익률 칼럼 (그대로, 100=본전)
- 올해 지수(ytd) = 연도별 누적 수익률 칼럼 (매년 1월 100 리셋)
- 목표 지수 = 년 목표금액 / BASE * 100
- 실제 원화 금액은 JSON에 기록하지 않는다 (공개 repo). 로그에도 원화 출력 금지.

TWR vs MWR (2026-08-07 추가):
시트의 누적/연도별 칼럼은 월수익률을 곱한 TWR이라 **자본 크기를 무시**한다. 작은 자본에
큰 %를 벌고 큰 자본에 큰 %를 잃으면 TWR은 플러스인데 실제 돈은 마이너스일 수 있다
(2026: TWR +18.5% vs 실제 손익 -82.2M). 그래서 금액가중수익률(MWR, Modified Dietz)을
함께 계산해 meta.mwrYtd / mwrInception 으로 내보낸다. 입출금 칼럼에는 신용 차입·상환도
포함되므로(2026-08-07 확인) 평가액(신용 포함) 기준과 정합한다.

진행중 월 처리: 시트의 수익금 = 다음달평가액 − 이번달평가액 − 입출금 이라, 다음 달 행이
비어 있으면 그 행은 -100%로 깨진다. 마지막 평가액 행은 항상 '진행중'으로 보고 성과 수치를
버린다(구조적 판정 — -100% 값 매칭에 의존하지 않는다).
"""
import csv
import datetime
import io
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def norm(h):
    return (h or "").replace(" ", "").replace("\n", "").strip()


def parse_num(s):
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("%", "")
    if not s or "#" in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def find_col(headers, pred):
    for i, h in enumerate(headers):
        if pred(norm(h)):
            return i
    return None


def cell(row, idx):
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def modified_dietz(months, ev):
    """금액가중수익률(%). months=[{'size':기초평가액,'dep':입출금}] 시간순, ev=기말 평가액.

    각 입출금은 해당 월 '초'에 발생한다고 가정한다(월별 데이터라 일자 미상).
    실제로 월 후반에 들어온 돈은 가중치가 과대평가되므로 결과는 보수적(덜 나쁜) 쪽이다.
    """
    n = len(months)
    if n == 0 or ev is None:
        return None
    bv = months[0]["size"]
    flows = [(x["dep"] or 0) for x in months]
    weighted = sum(f * (n - i) / n for i, f in enumerate(flows))
    denom = bv + weighted
    if denom <= 0:
        return None
    return (ev - bv - sum(flows)) / denom * 100


def main():
    url = os.environ.get("SHEET_CSV_URL")
    if not url:
        print("SHEET_CSV_URL 미설정 — 건너뜀 (수동 운영 중).")
        return

    raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))

    hidx = next((i for i, r in enumerate(rows) if any("평가액" in (c or "") for c in r)), None)
    if hidx is None:
        raise SystemExit("헤더 행('평가액')을 못 찾음 — CSV 구조 확인 필요")
    H = rows[hidx]
    print("헤더:", [norm(h) for h in H if norm(h)])  # 칼럼명만 (원화 없음)

    c_date = find_col(H, lambda h: "기준" in h)
    c_size = find_col(H, lambda h: h == "평가액")
    c_dep = find_col(H, lambda h: h == "입출금")
    c_mon = find_col(H, lambda h: h == "수익률")
    c_twr = find_col(H, lambda h: h == "누적수익률")
    c_ytd = find_col(H, lambda h: "연도별" in h)
    c_tgt = find_col(H, lambda h: "목표" in h)

    raw = []
    for r in rows[hidx + 1:]:
        d = cell(r, c_date)
        if not d:
            continue
        m = re.match(r"\s*(\d{4})-(\d{1,2})", d)
        if not m:
            continue
        size_won = parse_num(cell(r, c_size))
        if size_won is None:
            continue  # 미래/빈 행
        raw.append({
            "month": "{}-{:02d}".format(m.group(1), int(m.group(2))),
            "size": size_won,
            "dep": parse_num(cell(r, c_dep)) or 0,
            "twr": parse_num(cell(r, c_twr)),
            "ytd": parse_num(cell(r, c_ytd)),
            "mon": parse_num(cell(r, c_mon)),
            "tgt": parse_num(cell(r, c_tgt)),
        })

    if not raw:
        raise SystemExit("파싱된 데이터 행 없음 — CSV 구조 확인 필요")

    # 시트가 미래 월 행까지 현재 평가액으로 미리 채우는 경우가 있다(2026-08-31 확인:
    # 9월·10월 행에 동일 값이 들어가 9월이 '완료월 +0.0%'라는 유령 데이터로 잡혔다).
    # '이번 달 + 1'까지만 남긴다 — 다음 달 행은 기말 평가액(= 현재값) 제공용으로 필요하고,
    # 그 이후 행은 전부 수식 잔재다.
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)  # KST 기준
    cutoff = "{}-{:02d}".format(now.year + (now.month // 12), now.month % 12 + 1)
    dropped = [x["month"] for x in raw if x["month"] > cutoff]
    raw = [x for x in raw if x["month"] <= cutoff]
    if dropped:
        print("미래 행 제외:", ", ".join(dropped))

    base = raw[0]["size"]
    # 마지막 평가액 행 = '진행중' 월. 그 행의 수익금·수익률은 다음 달 평가액이 없어
    # -100%로 깨져 있으므로 성과 수치를 전부 버린다(값이 아니라 위치로 판정).
    last_i = len(raw) - 1
    series = []
    for i, x in enumerate(raw):
        done = i < last_i
        pnl_won = (raw[i + 1]["size"] - x["size"] - x["dep"]) if done else None
        series.append({
            "month": x["month"],
            "size": round(x["size"] / base * 100, 1),
            "twr": round(x["twr"], 1) if (done and x["twr"] is not None) else None,
            "ytd": round(x["ytd"], 2) if (done and x["ytd"] is not None) else None,
            "target": round(x["tgt"] / base * 100, 1) if x["tgt"] is not None else None,
            "monthly": round(x["mon"], 2) if (done and x["mon"] is not None) else None,
            "depositIdx": round(x["dep"] / base * 100, 1) if x["dep"] else 0,
            "pnlIdx": round(pnl_won / base * 100, 2) if pnl_won is not None else None,
        })

    # ── 금액가중수익률(MWR) — 완료된 월만 사용, 기말값 = 마지막(진행중) 행의 평가액
    complete, ev = raw[:last_i], raw[last_i]["size"]
    mwr_incep = modified_dietz(complete, ev)
    year = raw[last_i]["month"][:4]
    ytd_months = [x for x in complete if x["month"][:4] == year]
    mwr_ytd = modified_dietz(ytd_months, ev)
    pnl_ytd_idx = None
    if ytd_months:
        pnl_ytd = ev - ytd_months[0]["size"] - sum(x["dep"] for x in ytd_months)
        pnl_ytd_idx = round(pnl_ytd / base * 100, 2)

    eq = {
        "_comment": "월별 시계열. size=규모지수(평가액, 입금 포함, 첫 행=100), twr=누적성과지수(입금 제외), ytd=연도별 누적성과(매년 1월 리셋), target=목표지수, monthly=월간 수익률(%), depositIdx=입출금(지수), pnlIdx=그 달 손익(지수, 자본 크기 반영). 마지막 행은 진행중이라 성과 필드 null. 자동 갱신. 원화 비노출.",
        "base": series[0]["month"] + " = 100",
        "series": series,
    }
    with open(os.path.join(DATA, "equity.json"), "w", encoding="utf-8") as f:
        json.dump(eq, f, ensure_ascii=False, indent=2)
        f.write("\n")

    latest = series[-1]
    last_twr = next((s["twr"] for s in reversed(series) if s["twr"] is not None), None)
    last_ytd = next((s["ytd"] for s in reversed(series) if s["ytd"] is not None), None)

    meta_path = os.path.join(DATA, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["sizeIndex"] = latest["size"]
    if last_twr is not None:
        meta["twrCumulative"] = round(last_twr - 100, 1)
    if last_ytd is not None:
        meta["ytdReturn"] = round(last_ytd - 100, 2)
    if latest["target"] is not None:
        meta["targetIndex"] = latest["target"]
    if mwr_ytd is not None:
        meta["mwrYtd"] = round(mwr_ytd, 1)
    if mwr_incep is not None:
        meta["mwrInception"] = round(mwr_incep, 1)
    if pnl_ytd_idx is not None:
        meta["pnlIdxYtd"] = pnl_ytd_idx
    meta["asOfMonth"] = complete[-1]["month"] if complete else None
    meta["lastUpdated"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("갱신 완료: {}개월 · 완료월 {} · 규모지수 {}".format(
        len(series), meta.get("asOfMonth"), latest["size"]))
    print("  TWR  누적 {}% · 올해 {}%".format(meta.get("twrCumulative"), meta.get("ytdReturn")))
    print("  MWR  누적 {}% · 올해 {}%  (손익지수 {})".format(
        meta.get("mwrInception"), meta.get("mwrYtd"), meta.get("pnlIdxYtd")))


if __name__ == "__main__":
    main()
