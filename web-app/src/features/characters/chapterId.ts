import type { Panel } from "@/shared/types";

const toHex = (value: number): string => value.toString(16).padStart(8, "0");

export const buildChapterId = (panels: Panel[]): string => {
  let hash = 2166136261;
  for (const panel of panels) {
    const signature = `${panel.id}:${panel.order}:${panel.width}x${panel.height}`;
    for (let index = 0; index < signature.length; index += 1) {
      hash ^= signature.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
  }
  return `chapter_${toHex(hash >>> 0)}`;
};
