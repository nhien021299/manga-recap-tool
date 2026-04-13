Use the manga-recap-webtool plugin.

Task:
Optimize performance for a heavy image-processing workflow.

Hot path:
[describe detect / scan / extract / preview problem here]

Constraints:
- Keep main thread responsive
- No giant full-chapter bitmap
- Prefer worker-friendly changes
- Explain tradeoffs

What I want back:
1. Bottleneck analysis
2. Which skill(s) should be used
3. Low-risk optimizations first
4. Metrics to capture before and after
5. Code-level implementation notes
