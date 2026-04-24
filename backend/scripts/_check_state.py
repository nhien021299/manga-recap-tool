"""Quick script to inspect the current character state."""
import json, sys

path = r".temp/characters/cache/e71ad4f3410e/acd7a8873e2b950ce85ffefb3aaa05f110f8f1cb.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)

print(f"=== Clusters: {len(data.get('clusters', []))} ===")
for c in data.get("clusters", []):
    cid = c["clusterId"]
    label = c["displayLabel"]
    panels = c["occurrenceCount"]
    conf = c["confidenceScore"]
    flags = c["reviewFlags"]
    samples = c["samplePanelIds"]
    print(f"  {cid}: {label} | panels={panels} | conf={conf} | flags={flags}")
    print(f"    samplePanelIds: {samples}")

print()
providers = set()
dino_dims = set()
handcrafted_dims = set()
fallback_reasons = set()
for crop in data.get("crops", []):
    diag = crop.get("diagnostics", {})
    emb_diag = diag.get("embeddingDiagnostics", {})
    if emb_diag:
        providers.add(emb_diag.get("provider", "?"))
        if "dinoDimension" in emb_diag:
            dino_dims.add(emb_diag["dinoDimension"])
        if "handcraftedDimension" in emb_diag:
            handcrafted_dims.add(emb_diag["handcraftedDimension"])
    fallback = emb_diag.get("dinoFallbackReason")
    if fallback:
        fallback_reasons.add(fallback)

print(f"Embedding providers: {providers}")
print(f"DINOv2 dims: {dino_dims}")
print(f"Handcrafted dims: {handcrafted_dims}")
print(f"Fallback reasons: {fallback_reasons}")

# Show crop kinds per cluster
print("\n=== Crops per cluster ===")
cluster_crops = {}
for crop in data.get("crops", []):
    cid = crop.get("assignedClusterId", "unassigned")
    state = crop.get("assignmentState", "?")
    kind = crop.get("kind", "?")
    pid = crop.get("panelId", "?")
    cluster_crops.setdefault(cid, []).append(f"{pid}:{kind}:{state}")
for cid, items in sorted(cluster_crops.items()):
    print(f"  {cid}: {items}")
