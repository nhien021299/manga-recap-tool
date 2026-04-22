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

    const findTightBounds = (rect: { y: number; height: number }) => {
      let minX = width;
      let maxX = -1;
      let minY = height;
      let maxY = -1;

      for (let y = rect.y; y < rect.y + rect.height; y++) {
        let rowHasContent = false;
        for (let x = 0; x < width; x++) {
          const idx = (y * width + x) * 4;
          const brightness = (data[idx] * 0.299 + data[idx + 1] * 0.587 + data[idx + 2] * 0.114);
          if (brightness < threshold) {
            rowHasContent = true;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
          }
        }
        if (rowHasContent) {
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }

      if (minX > maxX || minY > maxY) {
        return {
          minX: 0,
          maxX: width - 1,
          minY: rect.y,
          maxY: rect.y + rect.height - 1,
        };
      }

      return { minX, maxX, minY, maxY };
    };

    // 3. Tight content bounds + low padding to avoid capturing too much white area.
    const finalRects = rects.map(rect => {
      const bounds = findTightBounds(rect);
      const contentWidth = bounds.maxX - bounds.minX + 1;
      const contentHeight = bounds.maxY - bounds.minY + 1;

      // Keep a very small breathing room, but bias toward tight crop.
      const paddingX = Math.max(2, Math.min(12, Math.floor(contentWidth * 0.01)));
      const paddingY = Math.max(2, Math.min(10, Math.floor(contentHeight * 0.01)));

      const finalX = Math.max(0, bounds.minX - paddingX);
      const finalY = Math.max(0, bounds.minY - paddingY);
      const finalWidth = Math.min(width - finalX, contentWidth + (paddingX * 2));
      const finalHeight = Math.min(height - finalY, contentHeight + (paddingY * 2));

      return {
        y: finalY,
        height: finalHeight,
        x: finalX,
        width: finalWidth
      };
    });

    self.postMessage({ type: 'SUCCESS', payload: finalRects });
  }

  if (type === 'SCAN_SAFE_BREAKS') {
    const { imageData, minGutterHeight = 20, threshold = 250 } = payload;
    const { width, height, data } = imageData;

    const safeBreaks: number[] = [];
    let whiteRowCount = 0;
    const noiseTolerance = 5;

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
          if (nonWhitePixels > noiseTolerance) break;
        }
      }

      const isWhiteRow = nonWhitePixels <= noiseTolerance;

      if (isWhiteRow) {
        whiteRowCount++;
      } else {
        if (whiteRowCount >= minGutterHeight) {
           const breakY = y - Math.floor(whiteRowCount / 2); // Middle of the gutter
           safeBreaks.push(breakY);
        }
        whiteRowCount = 0;
      }
    }

    self.postMessage({ type: 'SUCCESS', payload: safeBreaks });
  }
};
