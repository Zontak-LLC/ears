#!/usr/bin/env node
/*
 * ears-page: get a WAV out of a web page's Web Audio, without speakers.
 *
 *   ears-page <url-or-file> --expr "<js that starts the sound>" [--seconds N] [--rate 48000]
 *             [--wait ms] [--out x.wav]
 *
 * It opens the page in headless Chrome (Playwright), swaps AudioContext for an
 * OfflineAudioContext of N seconds before the page's scripts run, runs --expr,
 * renders the first context the page made and writes a 16-bit WAV.
 *
 * Playwright is found in this order: $EARS_PLAYWRIGHT (a folder that holds
 * node_modules/playwright or playwright-core, or the package folder itself), the
 * current folder, then the global npm root. Browser: $EARS_CHROME (path to a
 * Chrome/Chromium binary), else the installed Google Chrome ("chrome" channel),
 * else Playwright's own Chromium.
 */
import { execSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fs.realpathSync(fileURLToPath(import.meta.url)));

function usage(msg) {
  if (msg) console.error(`ears-page: ${msg}`);
  console.error('usage: ears-page <url-or-file> --expr "<js>" [--seconds N] [--rate 48000] [--wait ms] [--out x.wav]');
  process.exit(2);
}

function args(argv) {
  const o = { seconds: 2, rate: 48000, wait: 300, out: "ears-page.wav" };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--expr") o.expr = argv[++i];
    else if (a === "--seconds") o.seconds = Number(argv[++i]);
    else if (a === "--rate") o.rate = Number(argv[++i]);
    else if (a === "--wait") o.wait = Number(argv[++i]);
    else if (a === "--out") o.out = argv[++i];
    else if (a === "-h" || a === "--help") usage();
    else rest.push(a);
  }
  if (rest.length !== 1) usage("give one url or file");
  if (!o.expr) usage("--expr is required");
  o.target = rest[0];
  return o;
}

function loadPlaywright() {
  const bases = [];
  if (process.env.EARS_PLAYWRIGHT) bases.push(process.env.EARS_PLAYWRIGHT);
  bases.push(process.cwd(), here);
  try {
    bases.push(path.dirname(execSync("npm root -g", { encoding: "utf8" }).trim()));
  } catch {}
  for (const base of bases) {
    const req = createRequire(path.join(path.resolve(base), "noop.js"));
    for (const name of ["playwright", "playwright-core", path.resolve(base)]) {
      try {
        return req(name); // the last one: base is the package folder itself
      } catch {}
    }
  }
  console.error(
    "ears-page: Playwright not found. Run `npm i -g playwright-core` (uses your installed Chrome),\n" +
      "or set EARS_PLAYWRIGHT to a folder whose node_modules has playwright.",
  );
  process.exit(3);
}

async function launch(chromium) {
  const tries = [];
  if (process.env.EARS_CHROME) tries.push({ executablePath: process.env.EARS_CHROME });
  tries.push({ channel: "chrome" }, {});
  let last;
  for (const t of tries) {
    try {
      return await chromium.launch({ headless: true, ...t });
    } catch (e) {
      last = e;
    }
  }
  throw last;
}

const o = args(process.argv.slice(2));
const { chromium } = loadPlaywright();
const url = /^[a-z]+:\/\//i.test(o.target) ? o.target : pathToFileURL(path.resolve(o.target)).href;
const helper = fs.readFileSync(path.join(here, "ears-render.js"), "utf8");

const browser = await launch(chromium);
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.addInitScript({ content: `${helper}\nwindow.Ears.capture(${o.seconds}, ${o.rate});` });
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(o.wait);
  await page.evaluate(o.expr);
  const b64 = await page.evaluate(() => window.Ears.renderCaptured(0));
  fs.writeFileSync(o.out, Buffer.from(b64, "base64"));
  const n = await page.evaluate(() => window.Ears.contexts.length);
  console.log(`ears-page: wrote ${o.out} (${o.seconds} s at ${o.rate} Hz; the page made ${n} audio context(s))`);
  if (errors.length) console.error(`ears-page: page errors:\n  ${errors.join("\n  ")}`);
} finally {
  await browser.close();
}
