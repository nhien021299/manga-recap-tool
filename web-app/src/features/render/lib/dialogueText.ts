const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const stripSpeakerPrefix = (text: string, speaker?: string | null): string => {
  const stripped = text.trim().replace(/^["“”]+|["“”]+$/g, "");
  const normalizedSpeaker = speaker?.trim();
  if (!normalizedSpeaker) return stripped;

  return stripped
    .replace(new RegExp(`^\\s*["“”]?\\s*${escapeRegExp(normalizedSpeaker)}\\s*[:：-]\\s*`, "i"), "")
    .replace(/^["“”]+|["“”]+$/g, "")
    .trim();
};

export const stripDuplicateDialogueFromNarration = (
  narration: string,
  dialogue?: string | null,
  speaker?: string | null,
): string => {
  let narrationText = narration.trim();
  if (!dialogue?.trim()) return narrationText;

  const dialogueCore = stripSpeakerPrefix(dialogue, speaker);
  const candidates = new Set([dialogue.trim(), dialogueCore]);
  if (speaker?.trim() && dialogueCore) {
    candidates.add(`${speaker.trim()}: ${dialogueCore}`);
  }

  Array.from(candidates)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .forEach((candidate) => {
      narrationText = narrationText.replace(new RegExp(escapeRegExp(candidate), "gi"), "");
    });

  if (dialogueCore) {
    narrationText = narrationText.replace(/["“”]([^"“”]+)["“”]/gi, (match, quoted: string) =>
      quoted.toLowerCase().includes(dialogueCore.toLowerCase()) ? "" : match,
    );
  }

  const attributionNames = [
    speaker?.trim(),
    "hắn",
    "y",
    "gã",
    "nàng",
    "cô",
    "anh",
    "lão",
  ].filter(Boolean) as string[];
  const attribution = Array.from(new Set(attributionNames.map(escapeRegExp))).join("|");
  if (attribution) {
    narrationText = narrationText.replace(
      new RegExp(
        `(?:^|[\\s,.;:!?])(?:${attribution})\\s+` +
          "(?:noi|nói|hoi|hỏi|dap|đáp|quat|quát|thot len|thốt lên|gam giong|gằn giọng|lam bam|lẩm bẩm)" +
          "\\s*[,.;:!?]*\\s*$",
        "i",
      ),
      "",
    );
  }

  return narrationText
    .replace(/\s+([,.!?;:])/g, "$1")
    .replace(/([,.!?;:]){2,}/g, "$1")
    .replace(/\s+/g, " ")
    .replace(/^[\s,.;:!?]+|[\s,.;:!?]+$/g, "")
    .trim();
};
