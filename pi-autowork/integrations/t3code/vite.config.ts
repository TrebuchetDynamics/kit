import { t3PluginWeb } from '@t3tools/plugin-sdk/vite';
import { defineConfig } from 'vite';
export default defineConfig({ plugins: [t3PluginWeb({ entry: 'web.tsx', outDir: 'dist' })] });
