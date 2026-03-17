# equipment_system_v2_sets_regions.md

## Overview

Equipment system v2 including: - Rarity (COMMON, RARE, UNIQUE,
LEGENDARY) - Set bonuses - Region Prefix/Suffix system - Event Patch +
Snapshot Sync architecture

Server is Source of Truth (SoT). Client updates via event patch and
periodic snapshot sync.

LEGENDARY items are quest-only (no random drops).

------------------------------------------------------------------------

## Core Concepts

### Rarity

All equipment has rarity: - COMMON - RARE - UNIQUE - LEGENDARY (quest
only)

### Sets

Items with setId belong to a set. Set bonuses activate when
requiredCount is met.

### Region Affixes

Items may receive: - 0\~1 Prefix - 0\~1 Suffix

Affixes are selected based on location and profile.

------------------------------------------------------------------------

## ItemInstance Structure

``` ts
interface ItemInstance {
  instanceId: string;
  baseItemId: string;
  prefixAffixId?: string;
  suffixAffixId?: string;
  displayName: string;
}
```

------------------------------------------------------------------------

## Set Bonus Example

2 pieces: +5 Attack

3 pieces: +10 Attack +5% Crit

------------------------------------------------------------------------

## Region Affix Rules

COMMON: - 10% prefix - 5% suffix

RARE: - 25% prefix - 15% suffix

UNIQUE: - 35% prefix - 25% suffix

LEGENDARY: - No random affixes
