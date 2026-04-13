Use the scene-detection-heuristics skill from the manga-recap-webtool plugin.

Task:
Design or improve scene crop suggestions for a vertical webtoon chapter.

Context:
- Images are shown in a virtual vertical list
- We do not stitch the full chapter into one bitmap
- Some scenes may span the bottom of image A and the top of image B
- User can manually refine suggestions

What I want back:
1. Detection pipeline
2. Candidate scoring rules
3. A/B overlap detection rules
4. False positive and false negative risks
5. TypeScript-friendly pseudocode
