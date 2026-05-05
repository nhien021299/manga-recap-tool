import { staticFile } from "remotion";

export const resolveAssetPath = (path: string): string => {
  if (
    path.startsWith("http://") ||
    path.startsWith("https://") ||
    path.startsWith("blob:") ||
    path.startsWith("data:")
  ) {
    return path;
  }
  return staticFile(path);
};
