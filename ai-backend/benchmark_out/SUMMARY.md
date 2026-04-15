# OCR + Vision Benchmark Summary

Output directory: `D:\code\manhwa-recap-tool\ai-backend\benchmark_out`

| Model | Mode | Workload | Status | Run Score | Total Ms | Caption Ms | OCR Ms | Merge Ms | Script Ms | Avg Panel Ms | OCR Provider |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| qwen3-vl:4b | vision_only | 10 | completed | 0.699 | 91314 | 81981 | 0 | 0 | 9333 | 8198.1 | disabled |
| qwen3-vl:4b | vision_only | 30 | completed | 0.0 | 280966 | 245991 | 0 | 0 | 34975 | 8199.7 | disabled |
| qwen3-vl:4b | vision_only | 52 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| qwen3-vl:4b | vision_ocr | 10 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| qwen3-vl:4b | vision_ocr | 30 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| qwen3-vl:4b | vision_ocr | 52 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| qwen2.5vl:7b | vision_only | 10 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| qwen2.5vl:7b | vision_only | 30 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| qwen2.5vl:7b | vision_only | 52 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| qwen2.5vl:7b | vision_ocr | 10 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| qwen2.5vl:7b | vision_ocr | 30 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| qwen2.5vl:7b | vision_ocr | 52 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| gemma3:latest | vision_only | 10 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| gemma3:latest | vision_only | 30 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| gemma3:latest | vision_only | 52 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | disabled |
| gemma3:latest | vision_ocr | 10 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| gemma3:latest | vision_ocr | 30 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
| gemma3:latest | vision_ocr | 52 | failed | 0.0 | 0 | 0 | 0 | 0 | 0 | 0 | rapidocr |
