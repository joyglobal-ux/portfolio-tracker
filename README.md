# 포트폴리오 저널

언제 어디서나 접근하는 포트폴리오 추적 대시보드. **어디에 · 왜 · 결과 · 지금 무엇을 보는가**를 한 URL로.

배포: GitHub Pages (`joyglobal-ux.github.io/portfolio-tracker`)

## 구조

```
index.html              대시보드 (Chart.js CDN, 빌드 무)
data/
  meta.json             헤더 KPI · 원칙
  equity.json           월별 시계열 (규모지수 · 성과TWR · 목표)
  positions.json        현재 보유 (비중 · 테제 · 손절)
  journal.json          투자 저널 (매매 이벤트 · 회고)
  watchlist.json        워치리스트 (트리거 대기)
.github/workflows/snapshot.yml   숫자 자동 갱신 (Secret 필요)
scripts/update_snapshot.py       시트 CSV → JSON 변환
```

## 두 레이어

- **숫자 (규모·비중·수익률):** SSOT = 구글 스프레드시트 `자산관리` 시트. Action이 pull → 자동 갱신.
- **서사 (테제·저널·회고):** 대화에서 Claude가 JSON 커밋.

## 정직성 원칙

- **실제 원화 금액은 커밋하지 않음.** 모든 규모는 지수(2025-08 = 100).
- **수익률 = TWR 누적** (입금 분리). 보유종목 단순 합산(+27.73%)이 아니라 입금 효과를 걷어낸 순수 운용 수익률(+137.3%).

## 가동 (Go-live) 체크리스트

- [ ] GitHub repo 생성 + Pages 활성화 (Settings > Pages > main 브랜치)
- [ ] 시트에 `입출금` 칼럼 유지 (이미 있음 ✓)
- [ ] repo Secret `SHEET_CSV_URL` 등록 (자산관리 시트 게시 CSV) — 등록 전까지 수동 운영
- [ ] `scripts/update_snapshot.py` 칼럼 매핑 확정 후 workflow 활성화

*Jay × Claude · 2026-06-13*
