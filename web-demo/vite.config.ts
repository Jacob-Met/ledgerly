import { defineConfig } from 'vitest/config';
export default defineConfig({base:'./',build:{outDir:'dist',emptyOutDir:true},worker:{format:'es'},test:{environment:'node'}});