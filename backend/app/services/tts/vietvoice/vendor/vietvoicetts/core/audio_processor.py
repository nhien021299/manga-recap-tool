"""
Audio processing utilities for TTS inference
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from pydub import AudioSegment
from typing import List
import io

class AudioProcessor:
    """Handles audio processing operations"""
    
    @staticmethod
    def load_audio(path_or_bytes: str | bytes, sample_rate: int) -> np.ndarray:
        """Load and process audio file"""
        if isinstance(path_or_bytes, str):
            if not Path(path_or_bytes).exists():
                raise FileNotFoundError(f"Audio file not found: {path_or_bytes}")
            audio_segment = AudioSegment.from_file(path_or_bytes).set_channels(1).set_frame_rate(sample_rate)
        else:
            audio_segment = AudioSegment.from_file(io.BytesIO(path_or_bytes)).set_channels(1).set_frame_rate(sample_rate)
        audio = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
        return AudioProcessor.normalize_to_int16(audio)
    
    @staticmethod
    def normalize_to_int16(audio: np.ndarray) -> np.ndarray:
        """Normalize audio to int16 range with proper scaling to prevent clipping"""
        # Remove DC offset
        audio = audio - np.mean(audio)
        
        # Get maximum absolute value
        max_val = np.max(np.abs(audio))
        
        if max_val > 0:
            # Use 90% of max range to prevent clipping and allow headroom
            scaling_factor = 29491.0 / max_val  # 90% of 32767
            normalized_audio = audio * scaling_factor
        else:
            normalized_audio = audio
        
        return normalized_audio.astype(np.int16)
    
    @staticmethod
    def fix_clipped_audio(audio: np.ndarray) -> np.ndarray:
        """Fix clipped audio by reducing overall level"""
        # Check if audio is clipped
        max_val = np.max(np.abs(audio))
        if max_val >= 32767:
            # Reduce level to 80% to remove clipping
            scale_factor = 26214.0 / max_val  # 80% of 32767
            return (audio * scale_factor).astype(np.int16)
        return audio
    
    @staticmethod
    def save_audio(audio: np.ndarray, file_path: str, sample_rate: int) -> None:
        """Save audio to file"""
        output_dir = Path(file_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        sf.write(file_path, audio.reshape(-1), sample_rate, format='WAVEX')
    
    @staticmethod
    def concatenate_with_crossfade(generated_waves: List[np.ndarray], 
                                   cross_fade_duration: float, 
                                   sample_rate: int) -> np.ndarray:
        """Concatenate multiple audio waves with cross-fading"""
        if not generated_waves:
            return np.array([])
        
        if len(generated_waves) == 1:
            return generated_waves[0].reshape(-1)  # Flatten to 1D
        
        # Flatten all waves to 1D arrays
        flattened_waves = [wave.reshape(-1) for wave in generated_waves]
        
        if cross_fade_duration <= 0:
            # Simply concatenate
            return np.concatenate(flattened_waves)
        
        # Combine all generated waves with cross-fading
        final_wave = flattened_waves[0]
        for i in range(1, len(flattened_waves)):
            prev_wave = final_wave
            next_wave = flattened_waves[i]

            # Calculate cross-fade samples, ensuring it does not exceed wave lengths
            cross_fade_samples = int(cross_fade_duration * sample_rate)
            cross_fade_samples = min(cross_fade_samples, len(prev_wave), len(next_wave))

            if cross_fade_samples <= 0:
                # No overlap possible, concatenate
                final_wave = np.concatenate([prev_wave, next_wave])
                continue

            # Overlapping parts
            prev_overlap = prev_wave[-cross_fade_samples:]
            next_overlap = next_wave[:cross_fade_samples]

            # Fade out and fade in
            fade_out = np.linspace(1, 0, cross_fade_samples)
            fade_in = np.linspace(0, 1, cross_fade_samples)

            # Cross-faded overlap
            cross_faded_overlap = prev_overlap * fade_out + next_overlap * fade_in

            # Combine
            new_wave = np.concatenate(
                [prev_wave[:-cross_fade_samples], cross_faded_overlap, next_wave[cross_fade_samples:]]
            )

            final_wave = new_wave

        return final_wave

    @staticmethod
    def concatenate_with_crossfade_improved(generated_waves: List[np.ndarray], 
                                           cross_fade_duration: float, 
                                           sample_rate: int) -> np.ndarray:
        """Improved concatenation with better volume handling and smoother cross-fade"""
        if not generated_waves:
            return np.array([])
        
        if len(generated_waves) == 1:
            return generated_waves[0].reshape(-1)
        
        # Flatten all waves to 1D arrays and fix clipping
        flattened_waves = []
        for wave in generated_waves:
            flat_wave = wave.reshape(-1)
            # Fix clipped audio
            fixed_wave = AudioProcessor.fix_clipped_audio(flat_wave)
            flattened_waves.append(fixed_wave)
        
        if cross_fade_duration <= 0:
            return np.concatenate(flattened_waves)
        
        # Improved cross-fading with volume matching
        final_wave = flattened_waves[0]
        
        for i in range(1, len(flattened_waves)):
            prev_wave = final_wave
            next_wave = flattened_waves[i]

            # Calculate cross-fade samples
            cross_fade_samples = int(cross_fade_duration * sample_rate)
            cross_fade_samples = min(cross_fade_samples, len(prev_wave), len(next_wave))

            if cross_fade_samples <= 0:
                final_wave = np.concatenate([prev_wave, next_wave])
                continue

            # Get overlapping parts
            prev_overlap = prev_wave[-cross_fade_samples:]
            next_overlap = next_wave[:cross_fade_samples]
            
            # Match volume levels in overlap region more carefully
            prev_rms = np.sqrt(np.mean(prev_overlap.astype(np.float32) ** 2))
            next_rms = np.sqrt(np.mean(next_overlap.astype(np.float32) ** 2))
            
            if prev_rms > 100 and next_rms > 100:  # Only adjust if both have reasonable levels
                # Adjust next wave to match previous wave's volume
                volume_ratio = prev_rms / next_rms
                # Limit volume adjustment to prevent distortion
                volume_ratio = np.clip(volume_ratio, 0.7, 1.5)
                next_wave_adjusted = (next_wave.astype(np.float32) * volume_ratio).astype(np.int16)
                next_overlap = next_wave_adjusted[:cross_fade_samples]
            else:
                next_wave_adjusted = next_wave
                next_overlap = next_wave_adjusted[:cross_fade_samples]

            # Use cosine-based fade for smoother transition
            fade_out = np.cos(np.linspace(0, np.pi/2, cross_fade_samples)) ** 2
            fade_in = np.sin(np.linspace(0, np.pi/2, cross_fade_samples)) ** 2

            # Cross-faded overlap with proper data type handling
            cross_faded_overlap = (prev_overlap.astype(np.float32) * fade_out + 
                                   next_overlap.astype(np.float32) * fade_in).astype(np.int16)

            # Combine waves
            final_wave = np.concatenate([
                prev_wave[:-cross_fade_samples], 
                cross_faded_overlap, 
                next_wave_adjusted[cross_fade_samples:]
            ])

        return final_wave 