import { STRIP_WIDTH } from '@/types';
import type { VirtualStripImage } from '@/types';

export async function buildVirtualStrip(files: File[]): Promise<{ images: VirtualStripImage[], totalHeight: number }> {
  let globalY = 0;
  const images: VirtualStripImage[] = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const img = await createImageBitmap(file);
    const originalWidth = img.width;
    const originalHeight = img.height;

    const scale = STRIP_WIDTH / originalWidth;
    const scaledHeight = originalHeight * scale;

    const objectUrl = URL.createObjectURL(file);

    images.push({
      id: `img-${Date.now()}-${i}`,
      file,
      originalWidth,
      originalHeight,
      scaledHeight,
      globalY,
      objectUrl
    });

    globalY += scaledHeight;
  }

  return { images, totalHeight: globalY };
}
