import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Bind 127.0.0.1 rather than a bare IP on purpose: localhost counts as a
// "secure context", so navigator.getGamepads() is available and a real
// DualSense works. Over http on a raw IP the browser hides the Gamepad API.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: '127.0.0.1', port: 5173 },
});
