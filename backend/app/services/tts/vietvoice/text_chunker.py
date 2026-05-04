from __future__ import annotations

import re
from typing import List


class VietnameseSafeTextChunker:
    def __init__(self, max_chars: int = 100):
        if max_chars < 40:
            raise ValueError("max_chars should be >= 40 to preserve Vietnamese phrase meaning.")
        self.max_chars = max_chars

    def normalize_spaces(self, text: str) -> str:
        text = text.replace("\ufeff", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", " ", text)
        return text.strip()

    def chunk(self, text: str) -> List[str]:
        text = self.normalize_spaces(text)
        if not text:
            return []

        sentences = self._split_keep_delimiters(text, r"([.!?…。！？]+)")
        chunks: List[str] = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(sentence) <= self.max_chars:
                chunks.append(sentence)
                continue

            chunks.extend(self._split_long_sentence(sentence))

        final_chunks = []
        for c in chunks:
            if not c.strip():
                continue
            if not any(char.isalnum() for char in c):
                continue
            final_chunks.append(self._ensure_tts_sentence_end(c))
        return final_chunks

    def _split_keep_delimiters(self, text: str, delimiter_pattern: str) -> List[str]:
        parts = re.split(delimiter_pattern, text)
        result: List[str] = []
        buffer = ""

        for part in parts:
            if part is None or part == "":
                continue

            buffer += part

            if re.fullmatch(delimiter_pattern, part):
                result.append(buffer.strip())
                buffer = ""

        if buffer.strip():
            result.append(buffer.strip())

        return result

    def _split_long_sentence(self, sentence: str) -> List[str]:
        comma_parts = self._split_keep_delimiters(sentence, r"([,;:，；：]+)")
        chunks: List[str] = []
        buffer = ""

        for part in comma_parts:
            part = part.strip()
            if not part:
                continue

            candidate = f"{buffer} {part}".strip() if buffer else part

            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer.strip())
                    buffer = ""

                if len(part) <= self.max_chars:
                    buffer = part
                else:
                    chunks.extend(self._split_by_space(part))

        if buffer:
            chunks.append(buffer.strip())

        return chunks

    def _split_by_space(self, text: str) -> List[str]:
        words = text.split(" ")
        chunks: List[str] = []
        buffer = ""

        for word in words:
            word = word.strip()
            if not word:
                continue

            candidate = f"{buffer} {word}".strip() if buffer else word

            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer.strip())
                buffer = word

        if buffer:
            chunks.append(buffer.strip())

        return chunks

    def _ensure_tts_sentence_end(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text

        if text[-1] not in ".!?…。！？,;:，；：":
            return text + "."
        return text
