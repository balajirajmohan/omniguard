/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OMNIGUARD_API_BASE?: string;
  readonly VITE_OMNIGUARD_CONSOLE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
