import { copyFileSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const botDir = process.env.MAKEFUN_BOT_DIR ?? '/bot';
const outputDir = process.env.MAKEFUN_OUTPUT_DIR ?? '/output';
const source = join(botDir, 'POST.json');

let postUrl: unknown;
try {
  const post = JSON.parse(readFileSync(source, 'utf8')) as { url?: unknown };
  postUrl = post?.url;
} catch (error) {
  console.error(`Cannot read or parse ${source}: ${(error as Error).message}`);
  process.exit(1);
}

// Validate the submitted address first, so a missing or unrelated post never reaches the output directory.
if (
  typeof postUrl !== 'string' ||
  !/^https:\/\/x\.com\/[A-Za-z0-9_]{1,15}\/status\/\d+\/?(?:\?[^\s]*)?$/.test(postUrl)
) {
  console.error(`Invalid POST.json: url must be an X post address (https://x.com/<handle>/status/<numeric id>).`);
  process.exit(1);
}

try {
  mkdirSync(outputDir, { recursive: true });
  copyFileSync(source, join(outputDir, 'POST.json'));
} catch (error) {
  console.error(`Could not copy POST.json to ${outputDir}: ${(error as Error).message}`);
  process.exit(1);
}

console.log(`Submitted post: ${postUrl}`);
