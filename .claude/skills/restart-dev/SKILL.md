# 서버·클라 개발 프로세스 재시작

기존 graymar NestJS / Next dev 프로세스를 완전히 종료하고, 포트 점유를 해제한 뒤 서버(3000) + 클라이언트(3001)를 백그라운드로 재기동한다. 좀비 프로세스 누수 방지.

## 언제 사용

- 코드 변경 후 dev 서버를 다시 올려야 할 때
- `EADDRINUSE`/포트 충돌 또는 오래된 빌드가 붙어있는 것 같을 때
- 사용자가 "재시작해줘"라고 명시할 때

## 절차

### 1. 기존 프로세스 정리

```bash
pkill -f 'graymar/server.*nest.js start --watch' 2>/dev/null
pkill -f 'graymar/server.*pnpm start:dev' 2>/dev/null
pkill -f 'graymar/client.*next dev' 2>/dev/null
sleep 2
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:3001 | xargs kill -9 2>/dev/null
sleep 1
```

### 2. 백그라운드 기동 (Bash run_in_background)

```bash
# 서버
cd /Users/dohamsu/Workspace/graymar/server && pnpm start:dev
```

```bash
# 클라이언트
cd /Users/dohamsu/Workspace/graymar/client && pnpm dev --port 3001
```

두 명령 모두 `run_in_background: true`. 주의: `pnpm dev -- --port 3001` 은 next 가 추가 인자를 디렉터리로 해석해 실패. `pnpm dev --port 3001` 사용.

### 3. 준비 완료 대기 (Monitor)

```bash
until lsof -ti:3000 >/dev/null 2>&1 && lsof -ti:3001 >/dev/null 2>&1; do sleep 2; done
echo "both-ready"
echo "server:$(curl -s http://localhost:3000/v1/version | head -c 200)"
echo "client:$(curl -s -o /dev/null -w %{http_code} http://localhost:3001)"
```

Monitor 도구로 `until ... ; do sleep 2; done` 패턴을 사용해 동시 체크.

### 4. 결과 검증

- `server:{"server":"<sha>"...}` 에서 해시가 원하는 최신 커밋과 일치
- `client:200` 응답
- 양쪽 모두 확인되면 재시작 완료

## 주의

- 다른 프로젝트(`mdfile` 등)에서 3000/3001 를 점유하는 경우가 있음. `pkill` 에 워크스페이스 경로(`graymar/server`)를 포함해서 남의 프로세스는 건드리지 않음
- Slack 규칙: 사용자 명시 요청으로 재시작했으면 완료 시 `✅` 알림, 내부 정리성 재시작은 생략
- 포트 상수: 서버 3000, 클라 3001 (CLAUDE.md Development Commands 참조)
