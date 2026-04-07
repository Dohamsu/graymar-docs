#!/bin/bash
# graymar 서버 프로세스 정리 스크립트
# 서버 시작 전 좀비/고아 프로세스를 정리한다.

echo "🧹 graymar 서버 프로세스 정리 중..."

# 1. graymar NestJS/pnpm 좀비 전체 정리
pkill -f 'graymar/server.*nest.js start --watch' 2>/dev/null
pkill -f 'graymar/server.*pnpm start:dev' 2>/dev/null
sleep 1

# 2. 고아 node main.js 프로세스 정리 (PPID=1)
for pid in $(ps -eo pid,ppid,command | grep 'dist/src/main.js' | grep -v grep | awk '$2==1 {print $1}'); do
  echo "  고아 프로세스 kill: PID=$pid"
  kill -9 "$pid" 2>/dev/null
done
sleep 1

# 3. 포트 3000 점유 프로세스 정리 (cloudflared 제외)
for pid in $(lsof -ti:3000 2>/dev/null); do
  proc=$(ps -p "$pid" -o command= 2>/dev/null)
  if echo "$proc" | grep -q cloudflared; then
    echo "  cloudflared 유지: PID=$pid"
  else
    echo "  포트 3000 프로세스 kill: PID=$pid ($proc)"
    kill -9 "$pid" 2>/dev/null
  fi
done
sleep 1

# 4. 포트 3001 점유 (Next.js dev) 정리
lsof -ti:3001 | xargs kill -9 2>/dev/null

# 5. 결과 확인
REMAINING=$(ps aux | grep 'graymar/server' | grep -v grep | grep -v cloudflared | wc -l | tr -d ' ')
PORT3000=$(lsof -i:3000 2>/dev/null | grep -v cloudflared | grep LISTEN | wc -l | tr -d ' ')

if [ "$REMAINING" = "0" ] && [ "$PORT3000" = "0" ]; then
  echo "✅ 정리 완료 — 좀비 0개, 포트 3000 비어있음"
else
  echo "⚠️ 남은 프로세스: $REMAINING개, 포트 3000 리스너: $PORT3000개"
fi
