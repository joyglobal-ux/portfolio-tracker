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
- **서술 필드(thesis·note·stop·log body·title)에도 규모를 역산할 수 있는 숫자 금지** — 이 repo는 public이다.
  - 금지: **주수**(`N주`, `A→B주`), **원화 금액**(`X억`, `NN.NM`, `+NNM`), 주수+평단 조합
  - 허용: 비중(%), 수익률(%), 평단·주가 단독, 지수, 기간의 '주'(`4주 박스`, `2주 내`)
  - 수량 변화는 "일부 매도", "비중 2배", "잔여분"처럼 비율·서술로 쓴다.
  - 2026-10-19 위반이 발견돼 정리하고 이력을 초기화했다. 커밋 전에 `주`·`억`·`M` 숫자를 grep으로 확인할 것.
- **수익률 = TWR 누적** (입금 분리). 보유종목 단순 합산(+27.73%)이 아니라 입금 효과를 걷어낸 순수 운용 수익률(+137.3%).

## 데이터 금고 (2026-11-01~)

공개되는 데이터는 `data/vault.json`(AES-256-GCM 암호문) **하나뿐**이다. 평문 `data/*.json`은 `.gitignore`로 막혀 있고 이 맥과 Actions 실행 중에만 존재한다.

- 편집 전: `python scripts/vault.py decrypt` (원격 최신 vault → 평문)
- 편집 후: `python scripts/vault.py encrypt` → `git add data/vault.json` → 커밋
- 비밀번호: macOS 키체인 `polaris-vault`(로컬) / repo Secret `VAULT_PASSWORD`(Actions). 같은 값이어야 한다.
- 브라우저: 페이지에서 비밀번호를 한 번 넣으면 유도된 키만 그 기기에 기억(허브·배분판과 공유). "이 기기에서 잠그기"로 삭제.
- 비밀번호를 잊으면: 새 비밀번호로 키체인·Secret을 바꾸고 `vault.json`을 지운 뒤 encrypt (평문 원본은 맥과 구글 시트에 있다).

## 가동 (Go-live) 체크리스트

- [ ] GitHub repo 생성 + Pages 활성화 (Settings > Pages > main 브랜치)
- [ ] 시트에 `입출금` 칼럼 유지 (이미 있음 ✓)
- [ ] repo Secret `SHEET_CSV_URL` 등록 (자산관리 시트 게시 CSV) — 등록 전까지 수동 운영
- [ ] `scripts/update_snapshot.py` 칼럼 매핑 확정 후 workflow 활성화

*Jay × Claude · 2026-06-13*
