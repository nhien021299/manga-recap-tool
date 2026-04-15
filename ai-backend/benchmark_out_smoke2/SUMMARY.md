# OCR + Vision Benchmark Summary

Output directory: `D:\code\manhwa-recap-tool\ai-backend\benchmark_out_smoke2`

| Model | Mode | Workload | Status | Run Score | Total Ms | Caption Ms | OCR Ms | Merge Ms | Script Ms | Avg Panel Ms | OCR Provider |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| qwen3-vl:4b | vision_only | 10 | completed | 0.52 | 89880 | 80258 | 0 | 0 | 9622 | 8025.8 | disabled |
| qwen3-vl:4b | vision_ocr | 10 | completed | 0.69 | 100693 | 90024 | 7038 | 0 | 10669 | 9002.4 | rapidocr |
