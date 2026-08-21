/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OMNIGUARD_API_BASE?: string;
  readonly VITE_OMNIGUARD_DEMO_ROUTE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
