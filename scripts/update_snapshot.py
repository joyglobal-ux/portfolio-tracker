"""자산관리 시트 CSV를 pull해서 data/equity.json·meta.json(숫자 필드)을 갱신.

필요: SHEET_CSV_URL 환경변수(GitHub Secret) = 자산관리 탭 게시 CSV.

원칙:
- 규모 지수 = 평가액 / BASE * 100  (BASE = 첫 데이터 행 평가액 = 100)
- 성과 지수(twr) = 누적 수익률 칼럼 (그대로, 100=본전)
- 올해 지수(ytd) = 연도별 누적 수익률 칼럼 (매년 1월 100 리셋)
- 목표 지수 = 년 목표금액 / BASE * 100
- 실제 원화 금액은 JSON에 기록하지 않는다 (공개 repo). 로그에도 원화 출력 금지.
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

    base = None
    series = []
    for r in rows[hidx + 1:]:
        d = cell(r, c_date)
        if not d:
            continue
        m = re.match(r"\s*(\d{4})-(\d{1,2})", d)
        if not m:
            continue
        month = "{}-{:02d}".format(m.group(1), int(m.group(2)))
        size_won = parse_num(cell(r, c_size))
        if size_won is None:
            continue  # 미래/빈 행
        if base is None:
            base = size_won
        twr = parse_num(cell(r, c_twr))
        ytd = parse_num(cell(r, c_ytd))
        mon = parse_num(cell(r, c_mon))
        tgt = parse_num(cell(r, c_tgt))
        dep = parse_num(cell(r, c_dep))
        if mon is not None and mon <= -99.9:  # 진행중 월 아티팩트(-100%)
            twr = ytd = mon = None
        series.append({
            "month": month,
            "size": round(size_won / base * 100, 1),
            "twr": round(twr, 1) if twr is not None else None,
            "ytd": round(ytd, 2) if ytd is not None else None,
            "target": round(tgt / base * 100, 1) if tgt is not None else None,
            "monthly": round(mon, 2) if mon is not None else None,
            "depositIdx": round(dep / base * 100, 1) if dep else 0,
        })

    if not series:
        raise SystemExit("파싱된 데이터 행 없음 — CSV 구조 확인 필요")

    eq = {
        "_comment": "월별 시계열. size=규모지수(평가액, 입금 포함, 첫 행=100), twr=누적성과지수(입금 제외), ytd=연도별 누적성과(매년 1월 리셋), target=목표지수, monthly=월간 수익률(%), depositIdx=입출금(지수). 자동 갱신. 원화 비노출.",
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
    meta["lastUpdated"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("갱신 완료: {}개월 · 최신 {} · 규모지수 {} · 누적 +{}% · 올해 +{}%".format(
        len(series), latest["month"], latest["size"],
        meta.get("twrCumulative"), meta.get("ytdReturn")))


if __name__ == "__main__":
    main()
