# Rebuild products.json — Full Data Coverage

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild products.json from the already-processed grocery.json (23,589 products) to include ~10,480 products instead of the current 5,372 — nearly doubling coverage while keeping file size under 4 MB raw (0.8 MB gzipped).

**Architecture:** A new `rebuild_products.py` script reads `grocery.json`, filters to grocery categories, keeps all multi-store products + single-store products from major chains, preserves all existing fields (`up`, `ut`, `sc`), and writes a drop-in replacement `products.json`. The app code (`index.html`) needs zero changes — field names stay identical.

**Tech Stack:** Python 3, JSON

---

## Analysis Summary

| Strategy | Products | Raw Size | Gzipped | Code Changes |
|----------|----------|----------|---------|--------------|
| Current products.json | 5,372 | 2.2 MB | 0.5 MB | none |
| **Hybrid (CHOSEN)** | **10,480** | **3.8 MB** | **0.8 MB** | **none** |
| 2+ stores only | 6,775 | 3.0 MB | 0.6 MB | none |
| All grocery | 21,059 | 6.3 MB | 1.3 MB | none |

**Hybrid = all 2+ store grocery products (6,775) + single-store products from major chains (3,705)**

Why hybrid wins:
- Nearly **2x product coverage** (10,480 vs 5,372)
- Only **0.3 MB more gzipped** than current (0.8 vs 0.5 MB)
- Keeps single-store major chain products for browsing (Kaufland-only items, Lidl exclusives)
- All multi-store products enable real price comparison
- **Zero app code changes** — same field names, same structure

What we're adding (4,353 multi-store products currently missing):
- Astika beer (41 stores), Olimpus butter, Bioprogram tea, baby food, olive oil, wine, etc.
- 1,062 new Drinks, 677 Household, 390 Meat, 379 Pantry, 315 Canned...

What we're dropping:
- Tobacco (154 products) — not grocery
- Beauty (195 products) — not grocery
- Single-store products from non-major chains (rarely useful for comparison)

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `rebuild_products.py` | CREATE | New build script that reads grocery.json → products.json |
| `products.json` | OVERWRITE | The app's data file — from 5,372 to ~10,480 products |
| `index.html` | NO CHANGE | App code stays identical |

---

### Task 1: Create rebuild_products.py

**Files:**
- Create: `rebuild_products.py` (in worktree root)

- [ ] **Step 1: Write the rebuild script**

```python
#!/usr/bin/env python3
"""
rebuild_products.py — Rebuild products.json from grocery.json
Filters to grocery categories, keeps multi-store + major-chain single-store products.
Preserves all fields: id, name, nameEN, category, brand, size, prices, sale, stores, up, ut, sc
"""
import json, os, sys

GROCERY_JSON = os.path.join(os.path.dirname(__file__), "grocery.json")
# Also check parent dir (when running from worktree)
if not os.path.exists(GROCERY_JSON):
    GROCERY_JSON = "/Users/Presidential/Desktop/Spesti/grocery.json"

OUTPUT = os.path.join(os.path.dirname(__file__) or ".", "products.json")

GROCERY_CATS = {
    "Milk", "Butter", "White Cheese", "Yellow Cheese", "Yogurt",
    "Eggs", "Bread", "Meat", "Fish", "Produce", "Pantry", "Canned",
    "Drinks", "Household", "Snacks", "Baby", "Frozen", "Dairy"
}

MAJOR_CHAINS = {
    "kaufland", "lidl", "billa", "fantastico", "tmarket",
    "metro", "cba", "fresh_market", "ebag", "bulmag",
    "coop", "kam", "mareshki"
}

def main():
    with open(GROCERY_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    products = data["products"] if isinstance(data, dict) else data
    print(f"Loaded {len(products)} products from grocery.json")

    kept = []
    for p in products:
        cat = p.get("category", "")
        if cat not in GROCERY_CATS:
            continue
        stores = p.get("stores", 0)
        if stores >= 2:
            kept.append(p)
        elif stores == 1:
            # Keep single-store products only if they're from a major chain
            price_stores = set(p.get("prices", {}).keys())
            if price_stores & MAJOR_CHAINS:
                kept.append(p)

    # Sort: most stores first, then alphabetical
    kept.sort(key=lambda x: (-x.get("stores", 0), x.get("name", "")))

    # Deduplicate by ID
    seen = set()
    deduped = []
    for p in kept:
        if p["id"] not in seen:
            seen.add(p["id"])
            deduped.append(p)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False)

    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    multi = sum(1 for p in deduped if p.get("stores", 0) >= 2)
    single = len(deduped) - multi

    print(f"\n=== RESULTS ===")
    print(f"Total products: {len(deduped)}")
    print(f"  Multi-store (2+): {multi}")
    print(f"  Single-store (major chains): {single}")
    print(f"File size: {size_mb:.1f} MB")

    cats = {}
    for p in deduped:
        c = p.get("category", "")
        cats[c] = cats.get(c, 0) + 1
    print(f"\nBy category:")
    for c in sorted(cats.keys()):
        print(f"  {c}: {cats[c]}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `cd /Users/Presidential/Desktop/Spesti/.claude/worktrees/vibrant-tesla && python3 rebuild_products.py`
Expected: ~10,480 products, ~3.8 MB file

- [ ] **Step 3: Verify app still loads correctly**

Open preview, check:
- Products load in search
- Category counts are higher
- Price comparisons still work
- Unit prices still display

- [ ] **Step 4: Commit**

```bash
git add rebuild_products.py products.json
git commit -m "feat: rebuild products.json with 10K+ products from full grocery.json"
```

---

### Task 2: Verify data integrity

- [ ] **Step 1: Run validation checks**

```python
# Verify all required fields exist
python3 -c "
import json
with open('products.json') as f:
    data = json.load(f)
required = ['id','name','category','prices']
for p in data:
    for r in required:
        assert r in p, f'Missing {r} in {p.get(\"id\",\"?\")}'
print(f'All {len(data)} products have required fields')
has_up = sum(1 for p in data if p.get('up'))
print(f'Unit prices: {has_up}/{len(data)} ({100*has_up/len(data):.0f}%)')
"
```

- [ ] **Step 2: Test search for previously-missing items**

Search for items that the stress test couldn't find:
- "астика" (beer — was missing, now should be found at 41 stores)
- "олимпус масло" (butter)
- "биопрограма чай" (tea)
- "ганчев пюре" (baby food)
- "олио кристал" (cooking oil)

- [ ] **Step 3: Compare old vs new coverage**

```python
python3 -c "
import json
with open('/Users/Presidential/Desktop/Spesti/products.json') as f:
    old = json.load(f)
with open('products.json') as f:
    new = json.load(f)
old_ids = set(p['id'] for p in old)
new_ids = set(p['id'] for p in new)
print(f'Old: {len(old)} | New: {len(new)} | +{len(new)-len(old)} products')
print(f'All old products preserved: {old_ids.issubset(new_ids)}')
lost = old_ids - new_ids
if lost:
    print(f'WARNING: {len(lost)} products from old set not in new!')
"
```
