"""
Command-line interface for VietVoice TTS
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .core import ModelConfig
from .core.model_config import MODEL_GENDER, MODEL_GROUP, MODEL_AREA, MODEL_EMOTION
from .api import TTSApi


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="VietVoice TTS - Vietnamese Text-to-Speech",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Required arguments
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("output", help="Output audio file path")
    
    # Voice selection
    parser.add_argument("--gender", choices=MODEL_GENDER, help="Voice gender")
    parser.add_argument("--group", choices=MODEL_GROUP, help="Voice group/style")
    parser.add_argument("--area", choices=MODEL_AREA, help="Voice area/accent")
    parser.add_argument("--emotion", choices=MODEL_EMOTION, help="Voice emotion")
    
    # Reference audio
    parser.add_argument("--reference-audio", help="Path to reference audio file")
    parser.add_argument("--reference-text", help="Text corresponding to reference audio")
    
    # Speed and random seed
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier")
    parser.add_argument("--random-seed", type=int, default=9527, help="Random seed. This is important for keeping the same voice when synthesizing.")

    # Model settings. These are not recommended to change.
    parser.add_argument("--model-url", help="URL to download model from")
    parser.add_argument("--model-cache-dir", help="Directory to cache model files")
    parser.add_argument("--nfe-step", type=int, default=32, help="Number of NFE steps")
    parser.add_argument("--fuse-nfe", type=int, default=1, help="Fuse NFE steps")
    
    # Audio processing
    parser.add_argument("--cross-fade-duration", type=float, default=0.1, 
                       help="Cross-fade duration in seconds")
    parser.add_argument("--max-chunk-duration", type=float, default=15.0,
                       help="Maximum chunk duration in seconds")
    parser.add_argument("--min-target-duration", type=float, default=1.0,
                       help="Minimum target duration in seconds")
    
    # ONNX Runtime settings
    parser.add_argument("--inter-op-threads", type=int, default=0,
                       help="Number of inter-op threads")
    parser.add_argument("--intra-op-threads", type=int, default=0,
                       help="Number of intra-op threads")
    parser.add_argument("--log-severity", type=int, default=4,
                       help="Log severity level")
    
    args = parser.parse_args()
    
    # Validate reference audio/text
    if args.reference_audio and not args.reference_text:
        parser.error("--reference-text is required when using --reference-audio")
    if args.reference_text and not args.reference_audio:
        parser.error("--reference-audio is required when using --reference-text")
    
    try:
        # Create configuration
        config = create_config(args)
        
        # Create API instance
        api = TTSApi(config)
        
        # Synthesize speech
        duration = api.synthesize_to_file(
            text=args.text,
            output_path=args.output,
            gender=args.gender,
            group=args.group,
            area=args.area,
            emotion=args.emotion,
            reference_audio=args.reference_audio,
            reference_text=args.reference_text
        )
        
        print(f"✅ Synthesis complete! Duration: {duration:.2f}s")
        print(f"📄 Output saved to: {args.output}")
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def create_config(args) -> ModelConfig:
    """Create ModelConfig from command line arguments"""
    return ModelConfig(
        model_url=args.model_url or "https://huggingface.co/nguyenvulebinh/VietVoice-TTS/resolve/main/model-bin.pt",
        model_cache_dir=args.model_cache_dir or "~/.cache/vietvoicetts",
        nfe_step=args.nfe_step,
        fuse_nfe=args.fuse_nfe,
        speed=args.speed,
        random_seed=args.random_seed,
        cross_fade_duration=args.cross_fade_duration,
        max_chunk_duration=args.max_chunk_duration,
        min_target_duration=args.min_target_duration,
        inter_op_num_threads=args.inter_op_threads,
        intra_op_num_threads=args.intra_op_threads,
        log_severity_level=args.log_severity
    )


if __name__ == "__main__":
    main() 