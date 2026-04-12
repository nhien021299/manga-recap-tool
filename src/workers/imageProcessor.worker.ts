/**
 * Image Processing Worker
 * Handles heavy tasks like row scanning and panel slicing
 */

self.onmessage = async (e: MessageEvent) => {
  const { type, payload } = e.data;

  if (type === 'EXTRACT_PANELS_ROW_SCAN') {
    const { imageData, minGutterHeight = 20, threshold = 250 } = payload;
    const { width, height, data } = imageData;

    // 1 & 2. Find vertical panel boundaries by detecting ANY content (Priority 1: Preserve text/SFX)
    // A row is considered content if it has more than a few non-white pixels.
    // This prevents cutting through dialogue tails or protruding SFX.
    const rects = [];
    let contentStart = -1;
    let whiteRowCount = 0;
    const noiseTolerance = 5; // Allow max 5 noisy pixels before calling it content

    for (let y = 0; y < height; y++) {
      let nonWhitePixels = 0;
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const brightness = (r * 0.299 + g * 0.587 + b * 0.114);
        
        if (brightness < threshold) {
          nonWhitePixels++;
          if (nonWhitePixels > noiseTolerance) break; // Optimization: stop early
        }
      }

      const isWhiteRow = nonWhitePixels <= noiseTolerance;

      if (isWhiteRow) {
        whiteRowCount++;
      } else {
        if (contentStart === -1) {
          contentStart = y;
        } else if (whiteRowCount >= minGutterHeight) {
           const contentEnd = y - whiteRowCount;
           const h = contentEnd - contentStart;
           if (h > 50) { 
             rects.push({ y: contentStart, height: h });
           }
           contentStart = y;
        }
        whiteRowCount = 0;
      }
    }

    if (contentStart !== -1) {
      const contentEnd = height - whiteRowCount; 
      const h = contentEnd - contentStart;
      if (h > 50) {
        rects.push({ y: contentStart, height: h });
      }
    }

    // 3. Find horizontal boundaries and apply Smart Padding (Priority 2 & 3)
    const finalRects = rects.map(rect => {
      let minX = width;
      let maxX = 0;

      // Find exact content boundaries horizontally
      for (let y = rect.y; y < rect.y + rect.height; y++) {
        let rowMin = -1;
        let rowMax = -1;
        for (let x = 0; x < width; x++) {
          const idx = (y * width + x) * 4;
          const brightness = (data[idx] * 0.299 + data[idx + 1] * 0.587 + data[idx + 2] * 0.114);
          
          if (brightness < threshold) {
            if (rowMin === -1) rowMin = x;
            rowMax = x;
          }
        }
        if (rowMin !== -1 && rowMin < minX) minX = rowMin;
        if (rowMax !== -1 && rowMax > maxX) maxX = rowMax;
      }

      if (minX > maxX) {
        minX = 0;
        maxX = width - 1;
      }

      // Priority 3: Add Padding for Animation (Keyframing headroom)
      const paddingX = Math.floor(width * 0.04); // 4% screen width padding
      const paddingY = Math.floor(height * 0.02); // 2% screen height padding (or based on width)

      let finalY = Math.max(0, rect.y - paddingY);
      let finalHeight = Math.min(height - finalY, rect.height + (paddingY * 2));
      
      let finalX = Math.max(0, minX - paddingX);
      let finalWidth = Math.min(width - finalX, (maxX - minX + 1) + (paddingX * 2));

      return {
        y: finalY,
        height: finalHeight,
        x: finalX,
        width: finalWidth
      };
    });

    self.postMessage({ type: 'SUCCESS', payload: finalRects });
  }
};
