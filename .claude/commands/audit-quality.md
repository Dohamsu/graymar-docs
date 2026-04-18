# Audit Quality — 정량 품질 감사 (regex + 원문 대조)

30턴 벤치 등 run 데이터를 `scripts/audit_quality.py` 로 전수 감사한다.

`/quality-check` (서술 품질 정성 평가)와 역할 분리:
- `/quality-check`: 서술 일관성/NPC 대사/분위기 등 정성 평가 (1~5점)
- `/audit-quality`: 예외/금지어/세계관/FP 자동 분류 (실제/회색/FP)

## 사용법

| 입력 | 동작 |
|------|------|
| `/audit-quality <run_id>` | 지정 run의 전수 감사 + 심층 분류 |
| `/audit-quality --last` | 가장 최근 bench JSON에서 runId 자동 추출 |

## 절차

1. **정본 스크립트 확인**
   - `scripts/audit_quality.py` (v4, 심층 검사 내장) 만 사용.
   - 임시 `/tmp/audit_*.py` 작성 금지. 수정은 정본 스크립트에 반영.

2. **실행**
   ```bash
   python3 scripts/audit_quality.py <run_id>
   ```

3. **내부 3단계 자동 수행**
   - 1차 regex 탐지
   - 원문 50자 context 추출
   - `system-prompts.ts` grep → 명시 금지어 여부 확인
   - 대사 내부/외부, URL 내부 판정
   - 자동 분류: `real` / `gray` / `fp`

4. **리포트 해석**
   - `실제 위반 (real)`: 프롬프트 명시 금지어 + 서술 영역 → **반드시 수정 대상**
   - `회색지대 (gray)`: 프롬프트 미명시 또는 해석 애매 → **프롬프트 규칙 추가 검토**
   - `FP`: URL 내부/대사 내 정당 사용 등 → **무시 또는 스크립트 정밀화**

5. **(선택) 텔레그램 보고**
   - 결과 요약을 텔레그램으로 전송.

## 금지 사항 (워크플로우 규칙)

- **regex 매칭 = 위반 직결 보고 금지**. 항상 심층 검사 3단계 통과 후 판정.
- **수동 재검증 요청 전에 1차 보고에서 FP 자동 필터링 완료**되어야 한다.
- **새 감지 패턴 추가 시**:
  1. `system-prompts.ts` 금지어 명시 확인
  2. word boundary 포함한 regex로 딕셔너리에 추가
  3. `check_prompt_explicit()` 로 대조 가능한지 검증

## 예시 출력

```
[🎯 자동 분류 결과]
  ❌ 실제 위반 (real)   :   2건
  ⚠️  회색지대 (gray)    :   0건
  ✅ FP (false positive):   0건

[❌ 실제 위반 2건]
  [currency] 2건
    턴   5 "동전": ...동전 주머니를 쥔 당신의 손을...
         이유: system-prompts.ts 명시 금지어 + 서술 영역
```
