# AI Implementation Guidelines

## 기본 원칙

1.  서버가 상태의 단일 진실 소스 (SoT)
2.  LLM은 서술만 담당
3.  이벤트 결정은 서버 로직에서 수행

## 구현 위치

### Intent Parser

-   ParsedIntentV3 생성

### Event System

-   EventMatcher
-   Event Director 정책 적용

### Narrative Generator

-   서버 결과를 기반으로 장면 서술

## 금지 사항

-   LLM이 게임 상태 직접 변경
-   Procedural Event가 메인 플롯 변경
-   Incident 시스템 우회

## 권장 구현 순서

1.  Narrative Context Patch 적용
2.  Event Director 정책 추가
3.  Event Library 정비
4.  Procedural Event Extension 적용
