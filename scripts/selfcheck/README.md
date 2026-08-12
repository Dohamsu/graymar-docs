# 자기점검 하네스 (arch/101)

코드·문서·DB 3소스 정합 감사. **LLM 호출 0 · 포인트 0 · 서버 재시작 불필요.**

```bash
python3 scripts/selfcheck/invariants.py          # A족 — 불변식 감시
python3 scripts/selfcheck/content_consistency.py # E족 — 콘텐츠 정합
python3 scripts/audit_payload_keys.py --lifetime # B족 — 배선 감사 (arch/100 §16)
```

## 판정 규약

| 표기 | 뜻 |
|---|---|
| ✅ OK | 분모 N > 0 이고 위반 0 |
| ❌ VIOLATION | 위반 발견 — **원문 대조 후에만 결함으로 보고** |
| ❔ UNDECIDABLE | **분모 0** — 그 상태가 DB 에 없다. "정상"이 아니다 |
| ⚠️ ERROR | 질의 실패 |

**철칙 — 분모 없는 판정 금지.** `0/0` 은 통과가 아니라 판정 불가다.

## 오탐 이력 (디텍터가 배운 것)

| 회차 | 항목 | 오탐 | 원인 → 대책 |
|---|---|---|---|
| 1 | #45 엔진 리터럴 | 14/14 | enum·접두규약 예외 미구현 → 실제 팩 ID 대조 |
| 2 | #45 | 5/5 | enum 값이 콘텐츠 JSON 에도 존재 → db/types enum 멤버 제외 |
| 1 | #42 speechStyle | 1/4 | 정규식이 따옴표 쌍을 가로질러 매칭 → 쌍 내부만 + 호칭 제외 |
| 1 | #6 actionSlots | 분모 0 | jsonb 경로 오류 → `ui->actionSlots` |

디텍터 수정 시 이 표에 추가한다. **오탐을 못 줄이면 루프는 노이즈 생성기가 된다**
(arch/101 §5).
