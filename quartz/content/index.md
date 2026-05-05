---
title: Graymar Docs
---

# Graymar — LLM 기반 정치 음모 텍스트 RPG

이름 없는 용병이 항만 도시 **그레이마르**의 권력 투쟁을 거쳐 성장하는 턴제 텍스트 RPG.
서버가 모든 게임 로직을 결정론적으로 처리하고, LLM은 내러티브 텍스트만 생성한다.

## 빠른 진입

- [[CLAUDE]] — 프로젝트 전체 가이드 + 구현 단계 + Critical Invariants
- [[architecture/INDEX|Architecture INDEX]] — 도메인별 1문단 요약 + 상호 참조 맵
- [[guides/01_server_module_map|서버 모듈 맵]] — 95+ services 위치
- [[guides/02_client_component_map|클라이언트 컴포넌트 맵]] — 60 components

## 폴더 구조

| 폴더 | 내용 | 용도 |
|------|------|------|
| architecture/ | 통합 설계 문서 (49 md) | 실무 참조 |
| specs/ | 원본 상세 스펙 (17 md) | 정본 |
| guides/ | 코드 구현 지침 (8 md) | 서비스/컴포넌트 맵 |
| CLAUDE.md | 프로젝트 메인 가이드 | 개요 + 정책 + Phase Status |

## 최근 작업 (Implementation Phase Status)

> CLAUDE.md "Implementation Phase Status" 표 참조.
>
> 최신: A56 NPC Reaction Director + 어휘 폭주 해소 (2026-05-04)
> - 시그니처 어구 39.7% → 6.2%
> - 마이렐 패턴 0%
> - 마커 substring 합쳐짐 자동 복구

---

> 이 사이트는 [Quartz 4](https://quartz.jzhao.xyz/)로 빌드되었습니다.
