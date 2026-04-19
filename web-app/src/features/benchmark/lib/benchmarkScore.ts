import type { BenchmarkDimensionScore, BenchmarkRecord, Metrics, StoryMemory, TimelineItem } from "@/shared/types";

const SCRIPT_CHUNK_SIZE = 10;
const GENERIC_MARKERS = [
  "something",
  "someone",
  "a person",
  "thing happens",
  "co chuyen gi do",
  "mot nguoi",
  "co dieu gi do",
];

const clamp = (value: number, min = 0, max = 100): number => Math.min(max, Math.max(min, value));

const round = (value: number): number => Math.round(value * 100) / 100;

const scoreRange = (
  value: number,
  sweetMin: number,
  sweetMax: number,
  hardMin: number,
  hardMax: number
): number => {
  if (value < hardMin || value > hardMax) return 0;
  if (value >= sweetMin && value <= sweetMax) return 100;
  if (value < sweetMin) {
    return clamp(((value - hardMin) / Math.max(sweetMin - hardMin, 1)) * 100);
  }
  return clamp(((hardMax - value) / Math.max(hardMax - sweetMax, 1)) * 100);
};

const uniqueWordRatio = (text: string): number => {
  const words = text
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter(Boolean);
  if (words.length === 0) return 0;
  return new Set(words).size / words.length;
};

const getGrade = (score: number): "A" | "B" | "C" | "D" => {
  if (score >= 85) return "A";
  if (score >= 70) return "B";
  if (score >= 55) return "C";
  return "D";
};

const buildDimensionScores = (
  timeline: TimelineItem[],
  storyMemories: StoryMemory[],
  metrics: Metrics
): BenchmarkDimensionScore[] => {
  const panelCount = Math.max(metrics.panelCount || timeline.length, 1);
  const voiceovers = timeline.map((item) => item.scriptItem?.voiceover_text?.trim() || "");
  const filledPanels = voiceovers.filter(Boolean).length;
  const mergedVoiceoverText = voiceovers.filter(Boolean).join(" ");
  const totalWords = mergedVoiceoverText.split(/\s+/).filter(Boolean).length;
  const avgWordsPerPanel = totalWords / panelCount;
  const genericPanels = voiceovers.filter((text) =>
    GENERIC_MARKERS.some((marker) => text.toLowerCase().includes(marker))
  ).length;
  const expectedMemories = Math.max(1, Math.ceil(panelCount / SCRIPT_CHUNK_SIZE));
  const memoriesWithSummary = storyMemories.filter((item) => item.summary.trim().length > 0).length;
  const tokenPerPanel = metrics.totalTokens > 0 ? metrics.totalTokens / panelCount : 0;

  const coverageScore = clamp((filledPanels / panelCount) * 100);
  const densityScore = scoreRange(avgWordsPerPanel, 12, 34, 5, 55);
  const vocabularyScore = clamp(((uniqueWordRatio(mergedVoiceoverText) - 0.18) / 0.28) * 100);
  const usefulnessScore = clamp(
    densityScore * 0.45 + vocabularyScore * 0.25 + (1 - genericPanels / panelCount) * 30
  );
  const continuityScore = clamp(
    Math.min(storyMemories.length / expectedMemories, 1) * 70 +
      Math.min(memoriesWithSummary / expectedMemories, 1) * 30
  );
  const latencyScore = clamp(
    scoreRange(metrics.avgPanelMs || 0, 0, 2800, 0, 7000) * 0.65 +
      scoreRange(metrics.totalMs || 0, 0, 70000, 0, 240000) * 0.35
  );
  const stabilityPenalty =
    Math.min(metrics.retryCount * 10, 30) +
    Math.min(metrics.rateLimitedCount * 18, 36) +
    Math.min(metrics.throttleWaitMs / 1000, 20);
  const efficiencyScore = clamp(
    scoreRange(tokenPerPanel || 0, 0, 1400, 0, 2600) * 0.55 + (100 - stabilityPenalty) * 0.45
  );

  return [
    {
      key: "coverage",
      label: "Coverage",
      score: round(coverageScore),
      note: `${filledPanels}/${panelCount} panel co voiceover.`,
    },
    {
      key: "script_usefulness",
      label: "Script Usefulness",
      score: round(usefulnessScore),
      note: `${round(avgWordsPerPanel)} tu/panel, ${genericPanels} panel co wording qua chung chung.`,
    },
    {
      key: "continuity",
      label: "Story Continuity",
      score: round(continuityScore),
      note: `${storyMemories.length}/${expectedMemories} memory chunk duoc luu.`,
    },
    {
      key: "latency",
      label: "Latency",
      score: round(latencyScore),
      note: `avg ${round(metrics.avgPanelMs)} ms/panel, total ${round(metrics.totalMs / 1000)} s.`,
    },
    {
      key: "stability",
      label: "Stability + Efficiency",
      score: round(efficiencyScore),
      note: `${round(tokenPerPanel)} token/panel, retry ${metrics.retryCount}, 429 ${metrics.rateLimitedCount}.`,
    },
  ];
};

const buildHighlights = (scores: BenchmarkDimensionScore[], metrics: Metrics): string[] => {
  const sorted = [...scores].sort((left, right) => right.score - left.score);
  const highlights = sorted
    .filter((item) => item.score >= 75)
    .slice(0, 2)
    .map((item) => `${item.label} tot: ${item.note}`);

  if (metrics.batchSizeUsed > 0) {
    highlights.push(`Backend chay voi batch size ${metrics.batchSizeUsed}.`);
  }

  return highlights.slice(0, 3);
};

const buildWarnings = (scores: BenchmarkDimensionScore[], metrics: Metrics): string[] => {
  const warnings = scores
    .filter((item) => item.score < 65)
    .slice(0, 3)
    .map((item) => `${item.label} can cai thien: ${item.note}`);

  if (metrics.rateLimitedCount > 0) {
    warnings.push(`Co ${metrics.rateLimitedCount} lan rate limit, nen xem lai pacing hoac batch size.`);
  }

  return warnings.slice(0, 3);
};

export const buildCompletionLogText = (metrics: Metrics): string =>
  `Gemini script generation completed.\n\n${JSON.stringify(metrics, null, 2)}`;

export const createBenchmarkRecord = ({
  mangaName,
  timeline,
  storyMemories,
  metrics,
}: {
  mangaName?: string;
  timeline: TimelineItem[];
  storyMemories: StoryMemory[];
  metrics: Metrics;
}): BenchmarkRecord => {
  const mergedVoiceoverText = timeline
    .map((item) => item.scriptItem?.voiceover_text?.trim() || "")
    .filter(Boolean)
    .join(" ");
  const completionLogText = buildCompletionLogText(metrics);
  const dimensionScores = buildDimensionScores(timeline, storyMemories, metrics);
  const overallScore = round(
    dimensionScores.reduce((total, item) => {
      const weightMap: Record<string, number> = {
        coverage: 0.22,
        script_usefulness: 0.28,
        continuity: 0.14,
        latency: 0.22,
        stability: 0.14,
      };
      return total + item.score * (weightMap[item.key] || 0);
    }, 0)
  );
  const createdAt = new Date().toISOString();
  const title = `${mangaName?.trim() || "Benchmark"} ${new Date(createdAt).toLocaleString()}`;

  return {
    id: `benchmark-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title,
    createdAt,
    mangaName: mangaName?.trim() || undefined,
    panelCount: metrics.panelCount || timeline.length,
    mergedVoiceoverText,
    completionLogText,
    combinedText: `${mergedVoiceoverText}\n\n${completionLogText}`.trim(),
    metrics,
    overallScore,
    grade: getGrade(overallScore),
    dimensionScores,
    highlights: buildHighlights(dimensionScores, metrics),
    warnings: buildWarnings(dimensionScores, metrics),
  };
};
