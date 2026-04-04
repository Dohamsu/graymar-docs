#!/usr/bin/env python3
"""Generate portraits for SUB-tier NPCs using Gemini image generation."""

import os, sys, json, base64, time
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "server" / ".env"
OUTPUT_DIR = ROOT / "server" / "public" / "npc-portraits"

# Load API key
api_key = None
with open(ENV_PATH) as f:
    for line in f:
        if line.startswith("GEMINI_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break
if not api_key:
    print("ERROR: GEMINI_API_KEY not found")
    sys.exit(1)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"

# SUB NPC 12명: npcId → (파일명, 프롬프트)
SUB_NPCS = {
    "NPC_TOBREN": {
        "file": "tobren.png",
        "prompt": "Fantasy RPG character portrait, male, middle-aged warehouse manager with worried expression, rough hands from manual labor, family man, dark fantasy medieval port city, oil painting, bust shot, dark background, moody lighting, no text, no watermark, no people in background"
    },
    "NPC_MOON_SEA": {
        "file": "laira_kestel.png",
        "prompt": "Fantasy RPG character portrait, female, young quiet clerk with glasses, neat appearance, holding quill pen, ink-stained fingers, studious look, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_MIRELA": {
        "file": "mirela.png",
        "prompt": "Fantasy RPG character portrait, female, elderly herb seller woman, weathered kind face, herbal pouch around neck, 60 years old, market vendor, warm but cautious eyes, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_RENNICK": {
        "file": "rennick.png",
        "prompt": "Fantasy RPG character portrait, male, charming rogue tavern gossiper, ex-actor, mischievous grin, slightly disheveled, holding a tankard, charismatic but untrustworthy look, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_CAPTAIN_BREN": {
        "file": "captain_bren.png",
        "prompt": "Fantasy RPG character portrait, male, young military officer, neat uniform with captain insignia, strong jaw, idealistic but burdened expression, city guard, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_ROSA": {
        "file": "rosa.png",
        "prompt": "Fantasy RPG character portrait, female, warm-hearted orphanage caretaker, former teacher, kind gentle face, modest dress, caring maternal expression, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_INFO_BROKER": {
        "file": "shadow_broker.png",
        "prompt": "Fantasy RPG character portrait, male, mysterious information broker, deep hood covering face, only sharp eyes visible, shadowy figure, dark cloak, sinister but professional, dark fantasy medieval, oil painting, bust shot, very dark background, moody lighting, no text, no watermark"
    },
    "NPC_GUARD_CAPTAIN": {
        "file": "captain_bellon.png",
        "prompt": "Fantasy RPG character portrait, male, imposing garrison captain, silver-streaked beard, chess player intellectual look, authoritative military bearing, ornate officer armor, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_OWEN_KEEPER": {
        "file": "owen.png",
        "prompt": "Fantasy RPG character portrait, male, heavyset jolly tavern keeper, balding with thick arms, ex-sailor, warm friendly face, wiping a mug, apron-wearing, neutral ground host, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_SERA_DOCKS": {
        "file": "sera.png",
        "prompt": "Fantasy RPG character portrait, female, stern warehouse logistics manager, expressionless face, practical short hair, dock worker clothing, clipboard in hand, orphan-turned-pragmatist, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_DAME_ISOLDE": {
        "file": "dame_isolde.png",
        "prompt": "Fantasy RPG character portrait, female, elegant aristocratic widow, expensive jewelry, calculating sharp eyes behind a fan, strong perfume aura, high society queen, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
    "NPC_GUARD_FELIX": {
        "file": "felix.png",
        "prompt": "Fantasy RPG character portrait, male, very young naive guard soldier, fresh face, rural boy in city guard uniform, idealistic bright eyes, slightly too-big helmet, dark fantasy medieval, oil painting, bust shot, dark background, moody lighting, no text, no watermark"
    },
}


def generate_portrait(npc_id: str, info: dict) -> bool:
    payload = {
        "contents": [{"parts": [{"text": info["prompt"]}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": 1.0,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GEMINI_URL, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        candidates = result.get("candidates", [])
        if not candidates:
            print(f"  WARN: No candidates")
            return False

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                b64 = part["inlineData"]["data"]
                img_bytes = base64.b64decode(b64)
                out_path = OUTPUT_DIR / info["file"]
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                print(f"  OK: {info['file']} ({len(img_bytes)//1024}KB)")
                return True

        print(f"  WARN: No image in response")
        return False

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ERROR {e.code}: {body[:200]}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== SUB NPC Portrait Generation ({len(SUB_NPCS)} NPCs) ===\n")

    success = 0
    fail = 0
    for npc_id, info in SUB_NPCS.items():
        print(f"[{success+fail+1}/{len(SUB_NPCS)}] {npc_id} → {info['file']}")
        if generate_portrait(npc_id, info):
            success += 1
        else:
            fail += 1
        time.sleep(3)  # rate limit

    print(f"\n=== Done: {success} OK, {fail} FAIL ===")

    # Print NPC_PORTRAITS mapping for turns.service.ts
    print("\n=== NPC_PORTRAITS mapping (copy to turns.service.ts) ===")
    for npc_id, info in SUB_NPCS.items():
        print(f"  {npc_id}: '/npc-portraits/{info['file']}',")


if __name__ == "__main__":
    main()
