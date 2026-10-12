#!/usr/bin/env node
/**
 * Ensure next is on a patched 15.5.x release (see Next.js security advisories).
 * 15.5.27 is the first 15.5 release past the current high/critical ranges.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(join(root, "node_modules/next/package.json"), "utf8"));
const version = pkg.version;

function isPatchedNext(ver) {
  const [major, minor, patch] = ver.split(".").map(Number);
  if (major !== 15) return false;
  if (minor > 5) return false;
  if (minor < 5) return false;
  return patch >= 27;
}

if (!isPatchedNext(version)) {
  console.error(`next must be 15.5.27 or a later 15.5 patch (installed: ${version})`);
  process.exit(1);
}

console.log(`next ${version}: patched baseline ok`);
