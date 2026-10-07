//  @ts-check

import { tanstackConfig } from "@tanstack/eslint-config"

export default [
  {
    // Generated files, build output and vendored code
    ignores: [
      ".output/**",
      ".nitro/**",
      ".tanstack/**",
      ".vite/**",
      "dist/**",
      "src/routeTree.gen.ts",
      "src/api/schema.ts",
      // Vendored code (shadcn/ui components, chart primitives), kept as upstream
      "src/components/ui/**",
      "src/components/charts/**",
    ],
  },
  ...tanstackConfig,
]
