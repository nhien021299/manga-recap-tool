import re


def strip_speaker_prefix(text: str, speaker: str | None = None) -> str:
    stripped = text.strip().strip('"“”')
    if not speaker:
        return stripped

    return re.sub(
        rf'^\s*["“”]?\s*{re.escape(speaker.strip())}\s*[:：-]\s*',
        "",
        stripped,
        flags=re.IGNORECASE,
    ).strip().strip('"“”')


def strip_duplicate_dialogue_from_narration(
    narration: str,
    dialogue: str | None,
    speaker: str | None = None,
) -> str:
    narration_text = narration.strip()
    if not dialogue:
        return narration_text

    dialogue_core = strip_speaker_prefix(dialogue, speaker)
    candidates = {dialogue.strip(), dialogue_core}
    if speaker and dialogue_core:
        candidates.add(f"{speaker.strip()}: {dialogue_core}")

    for candidate in sorted((c for c in candidates if c), key=len, reverse=True):
        narration_text = re.sub(
            re.escape(candidate),
            "",
            narration_text,
            flags=re.IGNORECASE,
        )

    if dialogue_core:
        narration_text = re.sub(
            r'["“”]([^"“”]+)["“”]',
            lambda match: "" if dialogue_core.lower() in match.group(1).lower() else match.group(0),
            narration_text,
            flags=re.IGNORECASE,
        )

    attribution_names = []
    if speaker:
        attribution_names.append(re.escape(speaker.strip()))
    attribution_names.extend(["hắn", "y", "gã", "nàng", "cô", "anh", "lão"])
    attribution = "|".join(dict.fromkeys(name for name in attribution_names if name))
    if attribution:
        narration_text = re.sub(
            rf"(?:^|[\s,.;:!?])(?:{attribution})\s+"
            r"(?:noi|nói|hoi|hỏi|dap|đáp|quat|quát|thot len|thốt lên|gam giong|gằn giọng|lam bam|lẩm bẩm)"
            r"\s*[,.;:!?]*\s*$",
            "",
            narration_text,
            flags=re.IGNORECASE,
        )

    narration_text = re.sub(r"\s+([,.!?;:])", r"\1", narration_text)
    narration_text = re.sub(r"([,.!?;:]){2,}", r"\1", narration_text)
    narration_text = re.sub(r"\s+", " ", narration_text).strip(" ,.;:!?")
    return narration_text.strip()
