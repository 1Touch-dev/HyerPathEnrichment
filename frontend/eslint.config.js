const { FlatCompat } = require("@eslint/eslintrc");

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "src/lib/generated/**",
      "playwright-report/**",
      "test-results/**",
    ],
  },
  {
    // This is the first lint config introduced for this codebase; downgrade a
    // handful of pre-existing, repo-wide violations to warnings so `next lint`
    // completes cleanly instead of failing on a backlog unrelated to any
    // single change. New code should still avoid these where practical.
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-empty-object-type": "warn",
      "react/no-unescaped-entities": "warn",
    },
  },
];

module.exports = eslintConfig;
