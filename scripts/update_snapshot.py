"""자산관리 시트 CSV를 pull해서 data/equity.json·positions.json을 갱신.

가동 전 필요: SHEET_CSV_URL 환경변수(GitHub Secret). 시트 칼럼 매핑은
실제 게시 CSV 구조 확인 후 Claude가 채운다 (현재는 스캐폴드).

설계:
- 규모 지수 = 평가액 / BASE_KRW * 100  (BASE_KRW = 2025-08 평가액)
- 성과 지수(TWR) = 누적 수익률 칼럼 그대로
- 목표 지수 = 년 목표금액 / BASE_KRW * 100
- 실제 원화 금액은 JSON에 절대 기록하지 않는다 (공개 repo).
"""
import csv
import io
import json
import os
import urllib.request

BASE_KRW = 204_288_497  # 2025-08 평가액 = 지수 100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch_rows(url):
    raw = urllib.request.urlopen(url, timeout=20).read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))


def main():
    url = os.environ.get("SHEET_CSV_URL")
    if not url:
        print("SHEET_CSV_URL 미설정 — 자동 갱신 건너뜀 (수동 운영 중).")
        return
    # TODO: 실제 CSV 칼럼 인덱스 매핑 (기준월, 평가액, 입출금, 누적수익률, 월간수익률, 년목표금액)
    # rows = fetch_rows(url)
    # series = [...]
    # equity 경로에 기록
    print("스캐폴드 — CSV 칼럼 매핑 확정 후 활성화.")


if __name__ == "__main__":
    main()
