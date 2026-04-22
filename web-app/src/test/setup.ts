Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  writable: true,
  value: (() => {
    let counter = 0;
    return () => `blob:test-${counter += 1}`;
  })(),
});

Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  writable: true,
  value: () => undefined,
});
