Use the extract-compositor skill from the manga-recap-webtool plugin.

Task:
Implement cross-image extraction for a crop region that may span multiple source images.

Context:
- Region is stored in global coordinates
- Source images have naturalWidth, naturalHeight, globalYStart, globalYEnd
- We want a final PNG blob
- We must avoid stitching the whole chapter

What I want back:
1. The extraction algorithm
2. The intersection math
3. A TypeScript implementation
4. Memory-safety notes
5. Regression tests for edge alignment
