#!/usr/bin/env python3
"""Regenerate broken item images (portrait→item-only) using Gemini image generation."""

import os, sys, json, base64, time, re
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "server" / ".env"
OUTPUT_DIR = ROOT / "client" / "public" / "items"

# Load API key
api_key = None
with open(ENV_PATH) as f:
    for line in f:
        if line.startswith("GEMINI_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in server/.env")
    sys.exit(1)

# Items to regenerate: id → (name, description for prompt)
REGEN_ITEMS = {
    "item_minor_healing": {
        "name": "하급 치료제",
        "prompt": "A small glass potion bottle filled with pale green healing liquid, cork stopper, medieval alchemy style, simple herb label tied with twine"
    },
    "item_superior_healing": {
        "name": "상급 치료제",
        "prompt": "An ornate glass potion bottle filled with glowing crimson healing elixir, golden cap with wax seal, premium alchemy potion, intricate bottle design"
    },
    "item_smuggle_map": {
        "name": "밀수 경로 지도",
        "prompt": "A worn parchment map showing secret harbor routes, ink markings of hidden passages, folded edges, compass rose, aged paper with water stains"
    },
    "eq_rusty_blade": {
        "name": "녹슨 단검",
        "prompt": "A short rusty iron dagger with chipped blade, worn leather grip, visible rust and pitting on the metal, old and weathered combat knife"
    },
    "eq_merchant_ring": {
        "name": "상단 인장 반지",
        "prompt": "A heavy silver signet ring with merchant guild emblem engraved, ornate band with trade symbols, polished metal with aged patina"
    },
    "eq_merchant_cloak": {
        "name": "길드 외교관 망토",
        "prompt": "A rich navy blue diplomat's cloak with gold embroidery, fur-lined collar, guild crest clasp, draped over invisible mannequin showing the full garment shape"
    },
    "eq_merchant_ledger": {
        "name": "상인 길드 원장",
        "prompt": "A thick leather-bound merchant ledger book, brass corner protectors, guild emblem embossed on cover, ribbon bookmark, worn edges from frequent use"
    },
    "eq_patrol_armor": {
        "name": "순찰대 경갑",
        "prompt": "A light patrol guard armor set - chest plate with shoulder guards, riveted leather and iron plates, city guard insignia, displayed on armor stand"
    },
    "eq_shadow_cloak": {
        "name": "그림자 망토",
        "prompt": "A pitch-black shadow cloak with tattered edges, seems to absorb light, dark fabric with subtle purple shimmer, hood attached, mysterious and ethereal"
    },
    "eq_smuggler_dagger": {
        "name": "밀수업자의 단검",
        "prompt": "A sleek smuggler's dagger with curved blade, dark steel with hidden compartment in pommel, leather-wrapped handle, dock rope tied to guard"
    },
}

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"

def generate_item_image(item_id: str, info: dict) -> bool:
    """Generate a single item image using Gemini."""
    prompt = (
        f"RPG game item icon. IMPORTANT: Show ONLY the item object itself on a dark background. "
        f"Absolutely NO people, NO hands, NO fingers, NO human body parts. "
        f"Just the item floating or resting on a surface. "
        f"Dark fantasy painterly style, dramatic lighting, detailed texture. "
        f"Item: {info['prompt']}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": 0.8,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GEMINI_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Extract image from response
        candidates = result.get("candidates", [])
        if not candidates:
            print(f"  WARN: No candidates for {item_id}")
            return False

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                mime = part["inlineData"].get("mimeType", "image/png")
                b64 = part["inlineData"]["data"]
                img_bytes = base64.b64decode(b64)
                out_path = OUTPUT_DIR / f"{item_id}.png"
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                print(f"  OK: {out_path.name} ({len(img_bytes)//1024}KB)")
                return True

        print(f"  WARN: No image in response for {item_id}")
        return False

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ERROR {e.code}: {body[:200]}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print(f"=== Item Image Regeneration ({len(REGEN_ITEMS)} items) ===\n")
    success = 0
    fail = 0

    for item_id, info in REGEN_ITEMS.items():
        print(f"[{success+fail+1}/{len(REGEN_ITEMS)}] {info['name']} ({item_id})")
        if generate_item_image(item_id, info):
            success += 1
        else:
            fail += 1
        time.sleep(2)  # rate limit

    print(f"\n=== Done: {success} OK, {fail} FAIL ===")


if __name__ == "__main__":
    main()
