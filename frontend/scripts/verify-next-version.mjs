#!/usr/bin/env node
/**
 * Ensure next is on a patched 14.2.x+ release (see Next.js security advisories).
 * npm audit may still flag next until advisory metadata lists 14.2.35 as fixed.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(join(root, "node_modules/next/package.json"), "utf8"));
const version = pkg.version;

function isPatchedNext(ver) {
  const parts = ver.split(".").map(Number);
  const [major, minor, patch] = parts;
  if (major > 14) return true;
  if (major < 14) return false;
  if (minor > 2) return true;
  if (minor < 2) return false;
  return patch >= 35;
}

if (!isPatchedNext(version)) {
  console.error(`next must be >= 14.2.35 (installed: ${version})`);
  process.exit(1);
}

console.log(`next ${version}: patched baseline ok`);
