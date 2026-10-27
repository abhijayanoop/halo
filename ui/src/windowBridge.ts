// The pywebview side of the window: resize it from the page. In a plain browser
// (npm run dev) there is no bridge and this does nothing.
declare global {
  interface Window {
    pywebview?: { api?: { resize?: (width: number, height: number) => void } };
  }
}

export function resizeWindow(width: number, height: number): void {
  const send = () => window.pywebview?.api?.resize?.(width, height);
  if (window.pywebview?.api) {
    send();
  } else {
    // The bridge appears a moment after the page loads.
    window.addEventListener("pywebviewready", send, { once: true });
  }
}
