import { STRIP_WIDTH } from "@/types";
import type { Scene, VirtualStripImage } from "@/types";

export interface DetectedLocalRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ImageDetectionResult {
  image: VirtualStripImage;
  rects: DetectedLocalRect[];
  safeBreaks: number[];
}

interface SceneCandidate {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  imageIndex: number;
  localX: number;
  localY: number;
  localWidth: number;
  localHeight: number;
  confidence: number;
  boundaryLinked: boolean;
  mergeCandidate: boolean;
  splitCandidate: boolean;
  failureModes: Set<string>;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const mapFailureLabel = (flag: string): string => {
  if (flag === "narrow-content") return "content-width-low";
  if (flag === "near-image-boundary") return "boundary-fragment-risk";
  if (flag === "tiny-segment") return "tiny-scene-risk";
  if (flag === "very-tall-scene") return "tall-scene-split-needed";
  if (flag === "low-gap-merge-risk") return "adjacent-merge-candidate";
  if (flag === "cross-image-overlap") return "cross-image-linked";
  return flag;
};

const scoreRect = (
  rect: DetectedLocalRect,
  image: VirtualStripImage
): { confidence: number; failureModes: string[] } => {
  const heightRatio = rect.height / image.originalHeight;
  const widthCoverage = rect.width / image.originalWidth;
  const edgeThreshold = Math.max(30, Math.floor(image.originalHeight * 0.02));

  const nearTop = rect.y <= edgeThreshold;
  const nearBottom = rect.y + rect.height >= image.originalHeight - edgeThreshold;

  const sizeScore = clamp(1 - Math.abs(heightRatio - 0.24) / 0.24, 0, 1);
  const widthScore = clamp((widthCoverage - 0.25) / 0.7, 0, 1);
  const edgePenalty = (nearTop ? 0.08 : 0) + (nearBottom ? 0.08 : 0);

  const confidence = clamp(0.45 + 0.24 * sizeScore + 0.23 * widthScore - edgePenalty, 0.15, 0.98);

  const failureModes: string[] = [];
  if (widthCoverage < 0.32) failureModes.push("narrow-content");
  if (rect.height < 95) failureModes.push("tiny-segment");
  if (nearTop || nearBottom) failureModes.push("near-image-boundary");

  return { confidence, failureModes };
};

const splitRectBySafeBreaks = (
  rect: DetectedLocalRect,
  safeBreaks: number[],
  minSegmentHeight: number,
  maxSegmentHeight: number
): Array<{ y: number; height: number }> => {
  const start = rect.y;
  const end = rect.y + rect.height;
  const margin = Math.max(20, Math.floor(minSegmentHeight * 0.6));

  const relevantBreaks = safeBreaks
    .filter((breakY) => breakY > start + margin && breakY < end - margin)
    .sort((a, b) => a - b);

  if (relevantBreaks.length === 0) {
    return [{ y: start, height: rect.height }];
  }

  const segments: Array<{ y: number; height: number }> = [];
  let cursor = start;

  for (const breakY of relevantBreaks) {
    const segmentHeight = breakY - cursor;
    if (segmentHeight >= minSegmentHeight) {
      segments.push({ y: cursor, height: segmentHeight });
      cursor = breakY;
    }
  }

  if (end - cursor >= minSegmentHeight) {
    segments.push({ y: cursor, height: end - cursor });
  }

  if (segments.length <= 1) {
    // No reliable safe break found: hard split long segments to prefer shorter crops.
    if (rect.height > maxSegmentHeight) {
      const hardSegments: Array<{ y: number; height: number }> = [];
      let cursor = start;
      while (cursor < end) {
        const remaining = end - cursor;
        const nextHeight = remaining > maxSegmentHeight ? maxSegmentHeight : remaining;
        if (nextHeight < minSegmentHeight && hardSegments.length > 0) {
          hardSegments[hardSegments.length - 1].height += remaining;
          break;
        }
        hardSegments.push({ y: cursor, height: nextHeight });
        cursor += nextHeight;
      }
      return hardSegments;
    }

    return [{ y: start, height: rect.height }];
  }

  return segments;
};

const boundaryMergeAcrossImages = (
  candidatesByImage: SceneCandidate[][],
  detections: ImageDetectionResult[],
  stripWidth: number
) => {
  for (let i = 0; i < candidatesByImage.length - 1; i++) {
    const current = candidatesByImage[i];
    const next = candidatesByImage[i + 1];
    if (current.length === 0 || next.length === 0) continue;

    const tail = current[current.length - 1];
    const head = next[0];

    const currImage = detections[i].image;
    const tailBottomGap = currImage.originalHeight - (tail.localY + tail.localHeight);
    const headTopGap = head.localY;
    const boundaryThreshold = Math.max(30, Math.floor(currImage.originalHeight * 0.02));

    if (tailBottomGap > boundaryThreshold || headTopGap > boundaryThreshold) continue;

    const newBottom = head.y + head.height;
    const tailRight = tail.x + tail.width;
    const headRight = head.x + head.width;
    const mergedLeft = Math.min(tail.x, head.x);
    const mergedRight = Math.max(tailRight, headRight);

    tail.x = clamp(mergedLeft, 0, stripWidth);
    tail.width = clamp(mergedRight - tail.x, 1, stripWidth - tail.x);
    tail.height = newBottom - tail.y;
    tail.localX = Math.round(tail.x / (stripWidth / currImage.originalWidth));
    tail.localWidth = Math.round(tail.width / (stripWidth / currImage.originalWidth));
    tail.localHeight = Math.round(tail.height / (stripWidth / currImage.originalWidth));
    tail.boundaryLinked = true;
    tail.confidence = clamp((tail.confidence + head.confidence) / 2 + 0.08, 0.2, 0.99);
    tail.failureModes.add("cross-image-overlap");

    next.shift();
  }
};

const applyMergeAndSplitHeuristics = (candidates: SceneCandidate[], stripWidth: number) => {
  const minSceneHeight = Math.round(stripWidth * 0.12);
  const tinySceneHeight = Math.round(stripWidth * 0.18);
  const nearGapThreshold = Math.round(stripWidth * 0.02);
  const overlapThreshold = Math.round(stripWidth * 0.015);
  const preferredMaxHeight = Math.round(stripWidth * 1.35);

  let index = 0;
  while (index < candidates.length - 1) {
    const current = candidates[index];
    const next = candidates[index + 1];
    const gap = next.y - (current.y + current.height);

    if (gap < -overlapThreshold) {
      const mergedLeft = Math.min(current.x, next.x);
      const mergedRight = Math.max(current.x + current.width, next.x + next.width);
      current.x = clamp(mergedLeft, 0, stripWidth);
      current.width = clamp(mergedRight - current.x, 1, stripWidth - current.x);
      current.height = Math.max(current.y + current.height, next.y + next.height) - current.y;
      current.confidence = clamp((current.confidence + next.confidence) / 2 - 0.03, 0.1, 0.98);
      current.failureModes.add("low-gap-merge-risk");
      candidates.splice(index + 1, 1);
      continue;
    }

    const shouldAutoMerge =
      gap >= 0 &&
      gap <= nearGapThreshold &&
      (current.height < tinySceneHeight || next.height < tinySceneHeight) &&
      (current.height + next.height + Math.max(0, gap) <= preferredMaxHeight);

    if (shouldAutoMerge) {
      const mergedLeft = Math.min(current.x, next.x);
      const mergedRight = Math.max(current.x + current.width, next.x + next.width);
      current.x = clamp(mergedLeft, 0, stripWidth);
      current.width = clamp(mergedRight - current.x, 1, stripWidth - current.x);
      current.height = next.y + next.height - current.y;
      current.confidence = clamp((current.confidence + next.confidence) / 2 - 0.02, 0.1, 0.98);
      current.failureModes.add("low-gap-merge-risk");
      candidates.splice(index + 1, 1);
      continue;
    }

    if (gap >= 0 && gap <= nearGapThreshold) {
      current.mergeCandidate = true;
      next.mergeCandidate = true;
      current.failureModes.add("low-gap-merge-risk");
      next.failureModes.add("low-gap-merge-risk");
    }

    if (current.height > preferredMaxHeight) {
      current.splitCandidate = true;
      current.failureModes.add("very-tall-scene");
      current.confidence = clamp(current.confidence - 0.08, 0.1, 0.98);
    }

    index += 1;
  }

  return candidates.filter((candidate) => candidate.height >= minSceneHeight);
};

export const buildSceneSuggestions = (
  detections: ImageDetectionResult[],
  stripWidth: number = STRIP_WIDTH
): Scene[] => {
  const candidatesByImage: SceneCandidate[][] = [];
  let sceneCounter = 1;

  detections.forEach((item, imageIndex) => {
    const scale = stripWidth / item.image.originalWidth;
    const minLocalSegment = Math.max(90, Math.floor((stripWidth * 0.18) / scale));
    const maxGlobalHeight = stripWidth * 1.35;
    const maxLocalSegment = Math.max(minLocalSegment + 40, Math.floor(maxGlobalHeight / scale));

    const candidates: SceneCandidate[] = [];

    for (const rect of item.rects.sort((a, b) => a.y - b.y)) {
      const splitRects = rect.height * scale > maxGlobalHeight
        ? splitRectBySafeBreaks(rect, item.safeBreaks, minLocalSegment, maxLocalSegment)
        : [{ y: rect.y, height: rect.height }];

      if (splitRects.length > 1) {
        for (const segment of splitRects) {
          const baseScore = scoreRect({ ...rect, y: segment.y, height: segment.height }, item.image);
          candidates.push({
            id: `scene-auto-${Date.now()}-${sceneCounter++}`,
            x: rect.x * scale,
            y: item.image.globalY + segment.y * scale,
            width: rect.width * scale,
            height: segment.height * scale,
            imageIndex,
            localX: rect.x,
            localY: segment.y,
            localWidth: rect.width,
            localHeight: segment.height,
            confidence: clamp(baseScore.confidence + 0.04, 0.1, 0.98),
            boundaryLinked: false,
            mergeCandidate: false,
            splitCandidate: false,
            failureModes: new Set(baseScore.failureModes),
          });
        }
        continue;
      }

      const baseScore = scoreRect(rect, item.image);
      candidates.push({
        id: `scene-auto-${Date.now()}-${sceneCounter++}`,
        x: rect.x * scale,
        y: item.image.globalY + rect.y * scale,
        width: rect.width * scale,
        height: rect.height * scale,
        imageIndex,
        localX: rect.x,
        localY: rect.y,
        localWidth: rect.width,
        localHeight: rect.height,
        confidence: baseScore.confidence,
        boundaryLinked: false,
        mergeCandidate: false,
        splitCandidate: false,
        failureModes: new Set(baseScore.failureModes),
      });
    }

    candidatesByImage.push(candidates);
  });

  boundaryMergeAcrossImages(candidatesByImage, detections, stripWidth);

  const merged = applyMergeAndSplitHeuristics(
    candidatesByImage.flat().sort((a, b) => a.y - b.y),
    stripWidth
  );

  return merged.map((candidate) => ({
    id: candidate.id,
    x: clamp(candidate.x, 0, stripWidth),
    y: candidate.y,
    width: clamp(candidate.width, 1, stripWidth - clamp(candidate.x, 0, stripWidth)),
    height: candidate.height,
    isAuto: true,
    confidence: clamp(candidate.confidence, 0.1, 0.98),
    boundaryLinked: candidate.boundaryLinked,
    mergeCandidate: candidate.mergeCandidate,
    splitCandidate: candidate.splitCandidate,
    failureModes: Array.from(candidate.failureModes).map(mapFailureLabel),
  }));
};
