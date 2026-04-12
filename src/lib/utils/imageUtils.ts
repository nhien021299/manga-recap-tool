/**
 * Image processing utilities
 */

export async function imageToImageData(blob: Blob): Promise<ImageData> {
  const img = await createImageBitmap(blob);
  const canvas = new OffscreenCanvas(img.width, img.height);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get 2d context');
  
  ctx.drawImage(img, 0, 0);
  return ctx.getImageData(0, 0, img.width, img.height);
}

export async function cropImage(originalBlob: Blob, rect: { x: number, y: number, width: number, height: number }): Promise<Blob> {
  const img = await createImageBitmap(originalBlob);
  const canvas = new OffscreenCanvas(rect.width, rect.height);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get 2d context');

  ctx.drawImage(img, rect.x, rect.y, rect.width, rect.height, 0, 0, rect.width, rect.height);
  return canvas.convertToBlob({ type: 'image/jpeg', quality: 0.9 });
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export async function generateThumbnail(blob: Blob, maxDimension: number = 200): Promise<string> {
  const img = await createImageBitmap(blob);
  let width = img.width;
  let height = img.height;

  if (width > height) {
    if (width > maxDimension) {
      height *= maxDimension / width;
      width = maxDimension;
    }
  } else {
    if (height > maxDimension) {
      width *= maxDimension / height;
      height = maxDimension;
    }
  }

  const canvas = new OffscreenCanvas(width, height);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get 2d context');

  ctx.drawImage(img, 0, 0, width, height);
  const resizedBlob = await canvas.convertToBlob({ type: 'image/webp', quality: 0.7 });
  return await blobToBase64(resizedBlob);
}
