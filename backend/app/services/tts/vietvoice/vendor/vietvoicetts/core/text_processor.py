"""
Text processing utilities for TTS inference
"""

import re
import numpy as np
from pathlib import Path
from typing import List, Dict


class TextProcessor:
    """Handles text processing operations"""
    
    def __init__(self, vocab_path: str):
        self.vocab_char_map = self._load_vocab(vocab_path)
        self.vocab_size = len(self.vocab_char_map)
    
    def _load_vocab(self, vocab_path: str) -> Dict[str, int]:
        """Load vocabulary mapping from file"""
        if not Path(vocab_path).exists():
            raise FileNotFoundError(f"Vocabulary file not found: {vocab_path}")
            
        vocab_char_map = {}
        with open(vocab_path, "r", encoding="utf-8") as f:
            for i, char in enumerate(f):
                vocab_char_map[char.rstrip('\n')] = i
        return vocab_char_map
    
    def text_to_indices(self, texts: List[List[str]]) -> np.ndarray:
        """Convert text to indices using vocabulary mapping"""
        get_idx = self.vocab_char_map.get
        list_idx_tensors = [
            np.array([get_idx(c, 0) for c in text], dtype=np.int32) 
            for text in texts
        ]
        return np.stack(list_idx_tensors, axis=0)
    
    def calculate_text_length(self, text: str, pause_punc: str) -> int:
        """Calculate text length including pause punctuation weighting"""
        return len(text.encode('utf-8')) + 3 * len(re.findall(pause_punc, text))
    
    def clean_text(self, text: str) -> str:
        """Clean text to keep only readable characters"""
        # only keep readable characters in alphabet, vietnamese characters, space, punctuation
        alphabet_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        vietnamese_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệđìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỵỷỹýỳỵỷỹ"
        punctuation_chars = " .,!?'@$%&/:;()"
        all_valid_chars = alphabet_chars + alphabet_chars.upper() + vietnamese_chars + vietnamese_chars.upper() + punctuation_chars
        all_valid_chars = list(set(all_valid_chars))
        
        # replace all invalid characters with space using all_valid_chars and regex
        if "\n" in text:
            chunks = [chunk.strip() for chunk in text.split("\n") if chunk.strip()]
            for idx, chunk in enumerate(chunks):
                if not chunk.strip().endswith("."):
                    chunks[idx] = chunk.strip() + "."
            text = " ".join(chunks)

        text = re.sub(f"[^{''.join(all_valid_chars)}]", " ", text)
        text = text.strip()
        # replace ;:() with ,
        text = re.sub(r'[;:()]', ',', text)
        
        # make sure no duplicate ,.
        text = re.sub(r'\.+', '.', text)
        text = re.sub(r',+', ',', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Append . at the end of the text if it doesn't end with . or ? or ! or ,
        if not text.endswith(('.', '?', '!', ',')):
            text += '.'
        
        return text
    
    def chunk_text(self, text: str, max_chars: int = 135) -> List[str]:
        """Split text into chunks with maximum character limit"""
        # Split text into sentences
        sentences = []
        
        # Split by .?!
        for s in re.split(r'(?<=[.!?]) +', text.strip()):
            s = s.strip()
            if s:            
                if len(s) < max_chars:
                    sentences.append(s)
                    continue
                
                # split by commas
                for part in s.split(', '):
                    part = part.strip()
                    if part:
                        if not part.endswith(','):
                            part += ','
                            
                        # Make sure sentences are not too long, cut them if necessary
                        if len(part) < max_chars:
                            sentences.append(part)
                        else:
                            print(f"Warning: Part too long ({len(part)} chars), splitting further: {part[:50]}...")
                            num_parts = len(part) // max_chars + 1
                            part_length = len(part) // num_parts
                            for i in range(num_parts):
                                start = i * part_length
                                end = (i + 1) * part_length if i < num_parts - 1 else len(part)
                                sub_part = part[start:end].strip()
                                if sub_part:
                                    sentences.append(sub_part)
        
        if not sentences:
            return []
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed max_chars
            if current_chunk and len(current_chunk + " " + sentence) > max_chars:
                # Save current chunk and start new one
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        # Add the last chunk if it exists
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Post-process: merge very short chunks with adjacent ones
        final_chunks = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            
            # If chunk is very short (less than 4 words), try to merge
            if len(current.split()) < 4 and len(chunks) > 1:
                if i < len(chunks) - 1:
                    # Merge with next chunk if total doesn't exceed max_chars
                    next_chunk = chunks[i + 1]
                    merged = current + " " + next_chunk
                    if len(merged) <= max_chars:
                        final_chunks.append(merged)
                        i += 2  # Skip next chunk as it's been merged
                        continue
                elif i > 0 and final_chunks:
                    # Merge with previous chunk if total doesn't exceed max_chars
                    prev_chunk = final_chunks[-1]
                    merged = prev_chunk + " " + current
                    if len(merged) <= max_chars:
                        final_chunks[-1] = merged
                        i += 1
                        continue
            
            final_chunks.append(current)
            i += 1
        
        print(f"chunk_text: {len(final_chunks)} chunks: {[len(text) for text in final_chunks]}. Max chars: {max_chars}")
        return final_chunks 