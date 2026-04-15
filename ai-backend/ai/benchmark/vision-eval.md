# 📊 Vision Model Benchmark & Scoring Guide
> Manga Recap Tool - AI Backend Evaluation Protocol

This guide defines the evaluation criteria and workflow for identifying the **best vision/caption model** for the manga recap pipeline.

---

## 🎯 Objectives (Mục tiêu)

We aim to select a model that balances visual fidelity with operational efficiency based on:
- **Visual Fidelity**: Accurate description of panels, character actions, and scene context.
- **OCR/SFX Extraction**: Ability to transcribe text bubbles and sound effects.
- **Downstream Utility**: How well the captions facilitate high-quality script generation.
- **Performance**: Throughput of **<= 2 minutes** for a full chapter (60-80 panels).

---

## 🧠 Core Principles (Nguyên tắc)

> [!IMPORTANT]
> Avoid "gut feeling" evaluations. All candidates must be measured using a combination of heuristic and human metrics.

1. **Auto Scoring**: Quantitative analysis of caption density and structure.
2. **Manual Review**: Qualitative sanity checks on 15% of the dataset.
3. **Runtime Metrics**: Measuring latency across the entire pipeline.

---

## 📁 Dataset Specification

- **Input**: 1 standard manga chapter (approx. 50–60 panels).
- **Format**: Cropped individual panel images.
- **Structure**:
  ```text
  D:\Manhwa Recap\Tâm Ma\chapter 1 cropped\
  ├── panel_001.png
  ├── panel_002.png
  └── ...
  ```

---

## 🤖 Candidate Models

Currently prioritized models for benchmarking:
- `qwen2.5vl:7b`: Primary candidate (balance of speed/quality).
- `qwen3-vl:4b`: Optimized/Lightweight candidate.
- `gemma3:latest`: High-fidelity reference candidate.

---

## ⚙️ Standard Configuration

To ensure parity, use the following `.env` settings during benchmarks:

```env
# Pipeline Batching
AI_BACKEND_CAPTION_CHUNK_SIZE=1
AI_BACKEND_CAPTION_MAX_TOKENS=512

# Resilience & Timeouts
AI_BACKEND_VISION_TIMEOUT_SECONDS=60
AI_BACKEND_VISION_TIMEOUT_RETRIES=2

# Input Constraints
AI_BACKEND_VISION_MAX_WIDTH=768
AI_BACKEND_VISION_MAX_HEIGHT=1536
```

---

## 🧪 Testing Workflow (Luồng thực hiện)

### Step 1: Execute Benchmark Script
Run the evaluation script against the candidate models:
```powershell
python semi_auto_caption_benchmark.py `
  --images "D:\Manhwa Recap\Tâm Ma\chapter 1 cropped" `
  --models qwen2.5vl:7b qwen3-vl:4b gemma3:latest `
  --output ".\benchmark_out"
```

### Step 2: Collected Artifacts
The script will generate the following structure in `--output`:
```text
benchmark_out/
├── captions_raw.jsonl   # Raw AI responses
├── auto_scores.csv      # Heuristic calculation results
├── manual_review.csv    # Template for human scoring
├── summary.json         # Aggregated metrics
└── SUMMARY.md           # Visual report
```

---

## 📊 Evaluation Metrics

### Auto Scoring (Heuristic)
| Metric | Description | Weight |
| :--- | :--- | :--- |
| `specificity_score` | Level of detail in visual description. | 25% |
| `anti_generic_score` | Penalty for repetitive or vague phrases. | 20% |
| `action_score` | Detection of verb-active descriptions. | 20% |
| `emotion_score` | Recognition of character facial/emotional states. | 15% |
| `dialogue_proxy` | Presence of extracted text/SFX. | 20% |
| `brevity_penalty` | Fixed deduction for captions < 15 words. | - |

**Formula**: `overall_auto_score = (weighted_sum) - penalties`

### Manual Scoring (Sanity Check)
Review 10–15 samples per model in `manual_review.csv` on a 1–5 scale.

| Field | Scale | Description |
| :--- | :--- | :--- |
| `manual_specificity` | 1–5 | Depth of description. |
| `action_clarity` | 1–5 | Accurate tracking of character movement. |
| `manual_emotion` | 1–5 | Contextually appropriate emotional mapping. |
| `manual_dialogue` | 1–5 | Accuracy of OCR/Text transcription. |

---

## 🚨 Error Taxonomy (Critical Bugs)

Watch for these specific failure modes during review:
- **Hallucination**: Identifying non-existent entities (e.g., "monsters" in lens flares).
- **Genericism**: "A person standing", "Something happens".
- **Action Omission**: Failing to describe the primary event of the panel.
- **Structural Failure**: Inset panels merged with main panels.
- **Dialogue Mimicry**: Inventing text that isn't in the panel.

---

## ⏱️ Runtime Targets

| Panels | Max Allowable Latency |
| :--- | :--- |
| **10** | < 20s |
| **30** | < 60s |
| **60** | < 120s |

---

## 🏆 Decision Thresholds

### 🟢 PASS (Production Ready)
- `manual_specificity` ≥ 4/5.
- Dialogue accuracy ≥ 70%.
- Minimal hallucinations.
- Consistent formatting.
- Meets runtime targets.

### 🟡 MID (Hybrid Use)
- High quality but slow runtime.

### 🔴 FAIL (Discard)
- High generic output.
- Frequent hallucinations.
- Script generation fails due to poor input quality.