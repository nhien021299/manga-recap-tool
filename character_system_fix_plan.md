# PLAN FIX TRIỆT ĐỂ CHARACTER CLUSTERING ISSUE

> Mục tiêu: sửa lỗi gom nhầm nhiều nhân vật vào một group, giảm dữ liệu bẩn trước khi đưa vào prompt/script, tăng chất lượng character map để phục vụ flow manga recap image-to-script hiện tại.

---

## 0. Vấn đề hiện tại

Ảnh kết quả hiện tại cho thấy hệ thống chỉ tạo được một group nhân vật lớn, nhưng bên trong group có rất nhiều crop không cùng nhân vật:

- Nam mặt lạnh / tóc đen / đội mũ.
- Bé gái hoặc nhân vật mặt tròn.
- Nhân vật nữ tóc dài / mặt nghiêng.
- Quái/rết/sinh vật xanh.
- Crop bị che chữ, crop quá nhỏ, crop nửa mặt, crop body hoặc full panel.

Kết luận kỹ thuật:

```text
Detector không phải lỗi chính.
Lỗi chính nằm ở quality gate + embedding input + clustering + auto-merge.
```

Hiện pipeline đang gom nhầm vì hệ thống cho quá nhiều crop bẩn đi vào identity clustering. Đây là lỗi “cluster quá tham”, không phải lỗi UI.

---

## 1. Nguyên tắc fix cốt lõi

### 1.1. Over-split tốt hơn over-merge

Trong character system cho manga/manhwa:

```text
Tách dư 2 group cùng nhân vật => sửa dễ bằng merge.
Gom nhầm 5 nhân vật vào 1 group => làm bẩn toàn bộ character map.
```

Vì vậy tất cả threshold phải ưu tiên **strict-first**.

### 1.2. Không ép mọi crop vào nhân vật

Crop không đủ chắc chắn phải đi vào:

```text
unknown / ignored / candidate / needs_review
```

Không được ép vào group gần nhất chỉ vì nó “hơi giống”.

### 1.3. Face/head là identity chính

Chỉ các crop sau mới được tham gia tạo nhân vật:

```text
FACE clean crop
HEAD clean crop
```

Các crop sau không được tạo identity chính:

```text
BODY
FULL_PANEL
MONSTER
TEXT_BUBBLE
LOW_QUALITY
UNCERTAIN
```

Body/person fallback chỉ dùng để đánh dấu “có nhân vật xuất hiện trong panel”, không dùng làm căn cước nhân vật.

---

## 2. Flow mới cần áp dụng

```text
Input chapter panels
  ↓
Detect face/head/body candidates
  ↓
Normalize crop + calculate quality score
  ↓
Classify crop kind: face/head/body/monster/unknown
  ↓
Quality gate
  ↓
Identity embedding only for clean face/head
  ↓
Strict clustering
  ↓
Cluster purity check
  ↓
Outlier rejection
  ↓
Split impure cluster
  ↓
Small cluster handling
  ↓
Character registry
  ↓
UI review: Save + Lock / Merge / Split / Mark Unknown / Ignore
  ↓
Export clean character map to script prompt
```

---

## 3. Phase 1: thêm crop quality gate

### 3.1. Mục tiêu

Chặn crop bẩn trước khi embedding/cluster. Đây là lớp “cửa khẩu” quan trọng nhất.

### 3.2. Metadata cần lưu cho mỗi crop

Mỗi candidate crop cần có schema tối thiểu:

```ts
export type CharacterCropKind =
  | "face"
  | "head"
  | "body"
  | "monster"
  | "unknown";

export type CharacterCropQuality = {
  sharpness: number;
  brightness: number;
  contrast: number;
  sizeScore: number;
  occlusionScore: number;
  textBubblePenalty: number;
  edgeCutPenalty: number;
  finalScore: number;
};

export type CharacterCrop = {
  id: string;
  panelIndex: number;
  imagePath?: string;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  kind: CharacterCropKind;
  detectorConfidence: number;
  quality: CharacterCropQuality;
  embedding?: number[];
  clusterId?: string;
  status: "candidate" | "assigned" | "unknown" | "ignored" | "locked";
};
```

### 3.3. Quality score đề xuất

Công thức nhẹ, không cần LLM vision:

```ts
finalScore =
  0.25 * sizeScore +
  0.20 * sharpness +
  0.20 * contrast +
  0.15 * brightness +
  0.10 * occlusionScore -
  0.05 * textBubblePenalty -
  0.05 * edgeCutPenalty;
```

### 3.4. Rule chặn crop

```ts
const QUALITY_GATE = {
  minFaceSize: 48,
  minHeadSize: 64,
  minFaceQuality: 0.58,
  minHeadQuality: 0.62,
  minDetectorConfidence: 0.45,
  maxTextBubblePenalty: 0.45,
  maxEdgeCutPenalty: 0.55,
};
```

Rule:

```ts
function canEnterIdentityCluster(crop: CharacterCrop): boolean {
  if (crop.status === "ignored") return false;
  if (crop.kind !== "face" && crop.kind !== "head") return false;

  const minSize = crop.kind === "face"
    ? QUALITY_GATE.minFaceSize
    : QUALITY_GATE.minHeadSize;

  const minQuality = crop.kind === "face"
    ? QUALITY_GATE.minFaceQuality
    : QUALITY_GATE.minHeadQuality;

  if (crop.bbox.width < minSize || crop.bbox.height < minSize) return false;
  if (crop.quality.finalScore < minQuality) return false;
  if (crop.detectorConfidence < QUALITY_GATE.minDetectorConfidence) return false;
  if (crop.quality.textBubblePenalty > QUALITY_GATE.maxTextBubblePenalty) return false;
  if (crop.quality.edgeCutPenalty > QUALITY_GATE.maxEdgeCutPenalty) return false;

  return true;
}
```

### 3.5. Output kỳ vọng sau Phase 1

- Crop mờ, crop nhỏ, crop bị chữ che không còn vào group chính.
- Representative crops sạch hơn.
- Số group có thể tăng lên, nhưng độ bẩn giảm mạnh.

---

## 4. Phase 2: tách human / monster / non-character

### 4.1. Vấn đề cần xử lý

Trong screenshot, crop quái/rết/sinh vật xanh bị gom chung với nhân vật người. Đây là lỗi cực độc vì monster crop có texture khác nhưng vẫn có thể bị embedding coi là “manga face-like”.

### 4.2. Không dùng LLM vision

Không cần gọi LLM vision vì sẽ chậm. Dùng heuristic nhanh:

- Dominant color bất thường.
- Không có vùng da/mặt rõ.
- Nhiều texture lặp dạng côn trùng/vảy/rết.
- Shape quá dài hoặc quá nhiều chi tiết nhỏ.
- Không detect được eye-pair ổn định.

### 4.3. Monster heuristic nhẹ

```ts
export function classifyMonsterLikeCrop(cropImage: ImageData): boolean {
  const colorStats = getColorStats(cropImage);
  const edgeStats = getEdgeStats(cropImage);
  const faceLayout = estimateFaceLayout(cropImage);

  const greenDominant = colorStats.greenRatio > 0.42 && colorStats.skinLikeRatio < 0.18;
  const tooManyEdges = edgeStats.edgeDensity > 0.38;
  const noFaceLayout = faceLayout.eyePairScore < 0.25;

  return greenDominant || (tooManyEdges && noFaceLayout);
}
```

Rule:

```ts
if (classifyMonsterLikeCrop(cropImage)) {
  crop.kind = "monster";
  crop.status = "unknown";
}
```

### 4.4. Monster không mất dữ liệu

Không xoá monster. Chỉ không đưa vào human identity cluster.

Lưu vào bucket riêng:

```text
nonHumanCharacters / monsters / creatures
```

Sau này nếu cần script, prompt vẫn có thể biết “quái/rết xuất hiện ở scene X”, nhưng không làm bẩn nhân vật người.

---

## 5. Phase 3: chuẩn hóa crop trước khi embedding

### 5.1. Mục tiêu

Embedding phải nhìn đúng “căn cước”, không nhìn background, panel, chữ thoại.

### 5.2. Normalize crop

Trước khi tạo embedding:

```text
1. Expand bbox nhẹ 8-12% để giữ tóc/cằm.
2. Clamp bbox trong image.
3. Remove/ignore vùng text bubble nếu overlap quá cao.
4. Resize về size cố định.
5. Center crop theo face/head.
6. Convert consistent color mode.
```

Config:

```ts
const CROP_NORMALIZE_CONFIG = {
  faceExpandRatio: 0.10,
  headExpandRatio: 0.08,
  outputSize: 224,
  backgroundPadColor: "median",
  maxTextOverlap: 0.35,
};
```

### 5.3. Không dùng full panel embedding làm identity

Cấm logic kiểu:

```text
panel embedding => character identity
```

Full panel embedding chỉ dùng cho scene/script context, không dùng cho nhân vật.

---

## 6. Phase 4: embedding strategy

### 6.1. Embedding nên tách 2 loại

```ts
faceEmbedding: number[];
headEmbedding: number[];
visualDescriptor: {
  hairColor: string;
  hairShapeScore: number[];
  faceTone: string;
  eyeRegionHash: string;
  outfitDominantColor?: string;
};
```

### 6.2. Không chỉ dựa vào một embedding

Manga có nhiều nhân vật cùng nét vẽ. Nên distance tổng hợp:

```ts
combinedDistance =
  0.70 * embeddingCosineDistance +
  0.15 * hairDescriptorDistance +
  0.10 * faceToneDistance +
  0.05 * panelTemporalPenalty;
```

### 6.3. Temporal penalty

Nếu hai crop cách nhau quá xa nhưng không có bằng chứng mạnh, đừng merge quá dễ.

```ts
function temporalPenalty(aPanel: number, bPanel: number): number {
  const diff = Math.abs(aPanel - bPanel);
  if (diff <= 3) return 0.00;
  if (diff <= 10) return 0.02;
  return 0.04;
}
```

Lưu ý: temporal chỉ là phụ, không được dùng để ép cùng nhân vật.

---

## 7. Phase 5: strict clustering

### 7.1. Config đề xuất

```ts
export const CHARACTER_CLUSTER_CONFIG = {
  minClusterSize: 2,
  minSamples: 2,

  faceDistanceThreshold: 0.26,
  headDistanceThreshold: 0.22,
  mixedDistanceThreshold: 0.24,

  outlierDistanceThreshold: 0.30,
  maxClusterInternalDistance: 0.38,

  allowBodyForIdentity: false,
  allowPanelForIdentity: false,
  allowMonsterForHumanIdentity: false,

  keepSingletonAsUnknown: true,
  preferOverSplit: true,
};
```

### 7.2. Rule clustering

```ts
function canLinkCrops(a: CharacterCrop, b: CharacterCrop): boolean {
  if (!canEnterIdentityCluster(a)) return false;
  if (!canEnterIdentityCluster(b)) return false;

  const distance = getCombinedIdentityDistance(a, b);

  if (a.kind === "face" && b.kind === "face") {
    return distance <= CHARACTER_CLUSTER_CONFIG.faceDistanceThreshold;
  }

  if (a.kind === "head" && b.kind === "head") {
    return distance <= CHARACTER_CLUSTER_CONFIG.headDistanceThreshold;
  }

  return distance <= CHARACTER_CLUSTER_CONFIG.mixedDistanceThreshold;
}
```

### 7.3. Không merge dây chuyền quá dễ

Không dùng logic “A gần B, B gần C, vậy A cùng C” nếu cluster đã loãng.

Cần thêm purity check sau khi tạo cluster.

---

## 8. Phase 6: cluster purity check

### 8.1. Mục tiêu

Sau khi cluster xong, kiểm tra xem group có bị trộn nhiều identity không.

### 8.2. Prototype không lấy trung bình tất cả crop

Không nên dùng toàn bộ crop để tính prototype vì crop bẩn kéo lệch centroid.

Dùng top clean crops:

```ts
function buildClusterPrototype(crops: CharacterCrop[]): number[] {
  const clean = crops
    .filter(canEnterIdentityCluster)
    .sort((a, b) => b.quality.finalScore - a.quality.finalScore)
    .slice(0, 5);

  return robustMeanEmbedding(clean.map(c => c.embedding!));
}
```

### 8.3. Outlier rejection

```ts
function rejectClusterOutliers(cluster: CharacterCluster): {
  kept: CharacterCrop[];
  outliers: CharacterCrop[];
} {
  const prototype = buildClusterPrototype(cluster.crops);

  const kept: CharacterCrop[] = [];
  const outliers: CharacterCrop[] = [];

  for (const crop of cluster.crops) {
    const d = cosineDistance(crop.embedding!, prototype);

    if (d > CHARACTER_CLUSTER_CONFIG.outlierDistanceThreshold) {
      outliers.push({ ...crop, status: "unknown", clusterId: undefined });
    } else {
      kept.push(crop);
    }
  }

  return { kept, outliers };
}
```

### 8.4. Impure cluster split

Nếu group có độ phân tán quá lớn:

```ts
function isImpureCluster(cluster: CharacterCluster): boolean {
  const best = cluster.crops
    .filter(canEnterIdentityCluster)
    .sort((a, b) => b.quality.finalScore - a.quality.finalScore)
    .slice(0, 8);

  const maxD = maxPairwiseDistance(best);
  return maxD > CHARACTER_CLUSTER_CONFIG.maxClusterInternalDistance;
}
```

Nếu impure:

```text
Split cluster bằng agglomerative clustering strict hơn.
Nếu vẫn impure, đưa crop xa nhất sang unknown.
```

---

## 9. Phase 7: representative crops sạch

### 9.1. Representative crop phải là bằng chứng tốt nhất

Không lấy representative từ crop random. Chỉ lấy crop thỏa:

```text
face/head
quality cao
không bị text che
không monster
không quá tối
không quá nhỏ
không nằm quá sát mép panel
```

### 9.2. Scoring representative

```ts
function representativeScore(crop: CharacterCrop): number {
  const kindBonus = crop.kind === "face" ? 0.10 : 0.04;
  const assignedBonus = crop.status === "assigned" ? 0.05 : 0;

  return crop.quality.finalScore + kindBonus + assignedBonus;
}
```

### 9.3. Representative list

Mỗi character group chỉ nên show:

```text
Top 6-10 representative crops
```

Không show quá nhiều crop bẩn ở representative section vì user dễ lock nhầm.

---

## 10. Phase 8: small cluster và unknown handling

### 10.1. Singleton không tự thành character chính

Nếu chỉ có 1 crop:

```text
Không tạo Character chính ngay.
Đưa vào Candidate hoặc Unknown.
```

Trừ khi crop cực rõ:

```ts
if (crop.quality.finalScore >= 0.78 && crop.detectorConfidence >= 0.75) {
  createCandidateCharacter(crop);
} else {
  markUnknown(crop);
}
```

### 10.2. Candidate characters

UI nên có 3 cấp:

```text
Confirmed Characters
Candidate Characters
Unknown Crops
```

User chỉ cần review candidate, không bị một đống crop bẩn phá giao diện.

---

## 11. Phase 9: UI workflow cải tiến

### 11.1. Nút hiện có nên giữ

Các nút hiện tại vẫn đúng hướng:

```text
Save + Lock
Save Draft
Split
Mark Unknown
Ignore
```

Nhưng cần đổi logic:

- `Save + Lock`: group đã lock thì không bị auto-merge ở lần chạy sau.
- `Split`: split dựa trên selected crops hoặc sub-cluster tự động.
- `Mark Unknown`: crop/group không vào prompt character map.
- `Ignore`: loại khỏi toàn bộ pipeline.

### 11.2. Thêm cảnh báo cluster bẩn

Nếu group impure:

```text
⚠ Cluster may contain multiple identities
```

Trigger khi:

```text
max internal distance > 0.38
hoặc representative crops có nhiều visual modes
hoặc có monster/body crop trong group
```

### 11.3. Thêm “Auto Clean Group”

Button này chạy:

```text
reject outliers → split impure modes → move weak crops to unknown
```

---

## 12. Phase 10: character registry sạch cho script prompt

### 12.1. Không đưa toàn bộ crop vào prompt

Prompt không cần biết 21 crop. Chỉ cần character summary sạch.

Schema export:

```ts
export type CharacterPromptCard = {
  characterId: string;
  displayName: string;
  confidence: number;
  role: "main" | "supporting" | "minor" | "monster" | "unknown";
  firstSeenPanel: number;
  lastSeenPanel: number;
  panelRefs: number[];
  visualTags: string[];
  representativeImageIds: string[];
  locked: boolean;
};
```

### 12.2. Prompt character map gọn

Ví dụ output cho script service:

```text
CHARACTER MAP:
- C01: Nam tóc đen, ánh mắt lạnh, thường xuất hiện ở panel 9,10,12,14,28,33,36. Confidence cao.
- C02: Bé gái tóc sáng, mặt tròn, biểu cảm hoảng/hồn nhiên, xuất hiện ở panel 37,41. Confidence trung bình.
- C03: Nữ tóc dài, mặt nghiêng, xuất hiện ở panel 39,48. Confidence trung bình.
- M01: Sinh vật/rết xanh, không phải người, xuất hiện ở panel 23,27. Dùng như monster/entity, không merge với human.
```

### 12.3. Không nhét crop bẩn vào script prompt

Prompt chỉ nhận:

```text
confirmed + candidate high confidence
```

Không nhận:

```text
unknown / ignored / low quality / impure group
```

---

## 13. Phase 11: cache và reproducibility

### 13.1. Cache detection/embedding

Để không phải chạy lại nặng:

```text
.cache/character-system/{chapterHash}/crops.json
.cache/character-system/{chapterHash}/embeddings.json
.cache/character-system/{chapterHash}/clusters.json
.cache/character-system/{chapterHash}/user_edits.json
```

### 13.2. Stable ID

Character ID không nên random hoàn toàn. Dùng hash từ representative crop:

```ts
characterId = `C_${hash(bestRepresentativeCrop.embedding).slice(0, 8)}`;
```

### 13.3. User edits phải override auto

Nếu user lock hoặc ignore:

```text
auto pipeline không được lật lại quyết định đó.
```

---

## 14. Test plan theo chapter hiện tại

### 14.1. Test case chính

Dùng chapter 52 scene hiện tại.

Kỳ vọng sau fix:

```text
Không còn chỉ 1 group lớn.
Ít nhất 3-5 group/candidate hợp lý.
Monster/rết không nằm chung group human.
Bé gái không nằm chung nam tóc đen.
Nữ tóc dài không nằm chung nam tóc đen nếu không đủ bằng chứng.
Crop bẩn chuyển sang unknown.
```

### 14.2. Metrics cần log

```ts
export type CharacterClusteringMetrics = {
  totalPanels: number;
  totalDetectedCrops: number;
  identityEligibleCrops: number;
  rejectedLowQualityCrops: number;
  rejectedMonsterCrops: number;
  unknownCrops: number;
  confirmedClusters: number;
  candidateClusters: number;
  impureClustersBeforeClean: number;
  impureClustersAfterClean: number;
  avgClusterInternalDistance: number;
  maxClusterInternalDistance: number;
};
```

### 14.3. Target chất lượng

```text
Rejected low-quality/body/monster: tăng lên là tốt.
Impure clusters after clean: gần 0.
Confirmed clusters: không cần nhiều, nhưng phải sạch.
Unknown crops: được phép cao, miễn character chính sạch.
```

---

## 15. Acceptance criteria

Một bản fix được xem là đạt khi:

### Must-have

```text
[ ] Body/full panel không được tham gia identity clustering.
[ ] Monster/rết không bị merge với human.
[ ] Group nam tóc đen không chứa bé gái/nữ/quái.
[ ] Representative crops của mỗi group nhìn cùng identity.
[ ] Có unknown bucket cho crop không chắc.
[ ] Có outlier rejection sau clustering.
[ ] Có split impure cluster.
[ ] User lock/ignore được lưu và không bị auto ghi đè.
```

### Should-have

```text
[ ] UI cảnh báo cluster bẩn.
[ ] Auto Clean Group.
[ ] Metrics debug hiển thị trong dev mode.
[ ] Export prompt character map gọn, không phình token.
```

### Nice-to-have

```text
[ ] Creature/monster registry riêng.
[ ] Character timeline theo panel.
[ ] Manual merge/split có preview distance.
```

---

## 16. Thứ tự implement đề xuất

### Sprint 1: Fix bẩn nhất

```text
1. Thêm canEnterIdentityCluster().
2. Chặn body/full panel/monster khỏi identity clustering.
3. Thêm min quality + min size.
4. Siết threshold clustering.
5. Thêm unknown bucket.
```

Kết quả mong muốn: không còn “1 group nuốt cả chapter”.

### Sprint 2: Làm sạch cluster

```text
1. Thêm robust prototype.
2. Thêm outlier rejection.
3. Thêm max internal distance.
4. Thêm split impure cluster.
5. Representative crops chỉ lấy crop sạch.
```

Kết quả mong muốn: group sạch, ít crop dị dạng.

### Sprint 3: UI và review flow

```text
1. Thêm warning cluster bẩn.
2. Thêm Auto Clean Group.
3. Candidate/Unknown section rõ hơn.
4. Save + Lock override auto pipeline.
5. Persist user edits.
```

Kết quả mong muốn: user review nhanh, ít phải sửa tay.

### Sprint 4: nối vào script prompt

```text
1. Export CharacterPromptCard.
2. Chỉ gửi confirmed/candidate high-confidence vào script prompt.
3. Monster/entity tách riêng.
4. Giới hạn token bằng visual tags + panel refs.
```

Kết quả mong muốn: script gọi nhân vật nhất quán hơn, không tăng prompt quá nhiều.

---

## 17. Config final đề xuất

```ts
export const CHARACTER_SYSTEM_CONFIG = {
  cropGate: {
    minFaceSize: 48,
    minHeadSize: 64,
    minFaceQuality: 0.58,
    minHeadQuality: 0.62,
    minDetectorConfidence: 0.45,
    maxTextBubblePenalty: 0.45,
    maxEdgeCutPenalty: 0.55,
  },

  normalize: {
    faceExpandRatio: 0.10,
    headExpandRatio: 0.08,
    outputSize: 224,
    maxTextOverlap: 0.35,
  },

  clustering: {
    minClusterSize: 2,
    minSamples: 2,
    faceDistanceThreshold: 0.26,
    headDistanceThreshold: 0.22,
    mixedDistanceThreshold: 0.24,
    outlierDistanceThreshold: 0.30,
    maxClusterInternalDistance: 0.38,
    keepSingletonAsUnknown: true,
    preferOverSplit: true,
  },

  identity: {
    allowBodyForIdentity: false,
    allowPanelForIdentity: false,
    allowMonsterForHumanIdentity: false,
  },

  representative: {
    maxRepresentativeCrops: 10,
    minRepresentativeQuality: 0.65,
  },

  promptExport: {
    maxCharacters: 8,
    maxPanelRefsPerCharacter: 12,
    includeUnknown: false,
    includeLowConfidence: false,
    includeMonsterRegistry: true,
  },
};
```

---

## 18. File/module nên tạo hoặc sửa

Tên file có thể tùy theo cấu trúc repo hiện tại, nhưng nên tách module như sau:

```text
web-app/src/lib/character/config.ts
web-app/src/lib/character/types.ts
web-app/src/lib/character/cropQuality.ts
web-app/src/lib/character/cropNormalize.ts
web-app/src/lib/character/cropClassifier.ts
web-app/src/lib/character/identityDistance.ts
web-app/src/lib/character/clusterCharacters.ts
web-app/src/lib/character/cleanClusters.ts
web-app/src/lib/character/characterRegistry.ts
web-app/src/lib/character/exportPromptCards.ts
web-app/src/lib/character/metrics.ts
```

Nếu backend đang xử lý character system thì mirror cùng cấu trúc ở backend. Nhưng ưu tiên hiện tại nên giữ character detection/review ở frontend nếu app đang xử lý panel/crop trong browser, để giảm round-trip và dễ review.

---

## 19. Pseudocode end-to-end

```ts
export async function buildCharacterSystem(panels: PanelImage[]) {
  const candidates = await detectCharacterCandidates(panels);

  const enriched = candidates.map(candidate => {
    const cropImage = extractCrop(candidate);
    const quality = calculateCropQuality(cropImage, candidate.bbox);
    const kind = classifyCropKind(cropImage, candidate, quality);

    return {
      ...candidate,
      kind,
      quality,
      status: "candidate",
    } satisfies CharacterCrop;
  });

  const eligible = enriched.filter(canEnterIdentityCluster);
  const unknownInitial = enriched.filter(crop => !canEnterIdentityCluster(crop));

  const embedded = await embedIdentityCrops(eligible);

  const rawClusters = strictClusterCharacters(embedded, CHARACTER_SYSTEM_CONFIG.clustering);

  const cleaned = rawClusters.flatMap(cluster => {
    const rejected = rejectClusterOutliers(cluster);
    const clusterAfterReject = {
      ...cluster,
      crops: rejected.kept,
    };

    if (isImpureCluster(clusterAfterReject)) {
      return splitImpureCluster(clusterAfterReject);
    }

    return [clusterAfterReject];
  });

  const registry = buildCharacterRegistry({
    clusters: cleaned,
    unknownCrops: [...unknownInitial],
  });

  const metrics = calculateCharacterMetrics({
    candidates: enriched,
    eligible,
    rawClusters,
    cleanedClusters: cleaned,
    registry,
  });

  return {
    registry,
    metrics,
  };
}
```

---

## 20. Debug UI cần có

Nên thêm panel dev/debug nhỏ:

```text
Total crops: 84
Eligible identity crops: 31
Rejected low quality: 22
Rejected monster: 4
Unknown: 27
Raw clusters: 2
Clean clusters: 5
Impure before clean: 1
Impure after clean: 0
Max internal distance: 0.31
```

Khi nhìn con số này, sẽ biết pipeline đang bị nghẹt ở đâu.

---

## 21. Kết quả cuối mong muốn

Sau khi áp dụng plan này, output character system nên chuyển từ:

```text
1 group lớn chứa 21/21 crop lẫn nhiều nhân vật
```

sang:

```text
3-5 confirmed/candidate character groups sạch hơn
1 monster/entity group riêng nếu cần
nhiều unknown crop hơn nhưng không làm bẩn nhân vật chính
representative crops nhất quán hơn
prompt character map ngắn hơn, sạch hơn, ít gây hallucination tên/nhân vật
```

Đây là hướng fix đúng vì nó xử lý tận gốc: **lọc trước, cluster chặt, kiểm tra sau, rồi mới export prompt**.

---

## 22. Ưu tiên thực thi ngay

Nếu chỉ làm trong một lượt sửa, ưu tiên đúng 5 việc này:

```text
1. Thêm canEnterIdentityCluster(): chỉ face/head sạch mới vào cluster.
2. Chặn body/full panel/monster khỏi identity.
3. Siết distance threshold xuống khoảng 0.22-0.28.
4. Thêm outlier rejection với threshold 0.30.
5. Thêm split impure cluster nếu max pairwise distance > 0.38.
```

Chỉ riêng 5 điểm này đã có khả năng sửa phần lớn lỗi trong screenshot hiện tại.
