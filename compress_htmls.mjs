// tools/compress_htmls.mjs
import { promises as fs } from "fs";
import path from "path";
import zlib from "zlib";
import { minify } from "html-minifier-terser";

const WEB_DIR = path.resolve("html");        // <-- adjust if needed
const OUT_H   = path.resolve("./htmls.h");// output header

const MINIFY_OPTIONS = {
  collapseWhitespace: true,
  removeComments: true,
  removeRedundantAttributes: true,
  removeEmptyAttributes: true,
  removeScriptTypeAttributes: true,
  removeStyleLinkTypeAttributes: true,
  minifyCSS: true,
  minifyJS: true,
  decodeEntities: true,
};

// --- Gzip size-regression gate -------------------------------------------------
// Each embedded page is served from PROGMEM on flash-constrained targets (ESP8266
// ETHER_BUFFER_SIZE=2048). Pin a per-page gzip budget so accidental bloat fails the
// PlatformIO prebuild (run_prebuild.py halts the build on non-zero exit) instead of
// silently eating flash. Tighten budgets as pages shrink; raise deliberately (with
// review) if a page legitimately needs to grow. Every .html MUST declare a budget.
const GZ_SIZE_BUDGETS = {
  "ap_home.html": 3072,   // Wi-Fi setup (AP mode)
  "update.html":  4096,   // OTA firmware upload (bundles a vanilla MD5 impl)
};

function toCIdent(name) {
  return name.replace(/[^a-zA-Z0-9_]/g, "_").replace(/^(\d)/, "_$1");
}
function toPathKey(file) {
  return "/" + path.basename(file);
}
function chunkBytes(arr, per = 16) {
  const out = [];
  for (let i = 0; i < arr.length; i += per) {
    const slice = arr.slice(i, i + per).map(v => `0x${v.toString(16).padStart(2,"0")}`);
    out.push(slice.join(", "));
  }
  return out.join(",\n  ");
}

async function main() {
  console.log("--------------------------------------------------");
  console.log("OpenSprinkler HTML Compressor");
  console.log("--------------------------------------------------");

  const files = (await fs.readdir(WEB_DIR))
    .filter(f => f.endsWith(".html"))
    .sort();

  let totalOrig = 0;
  let totalGz   = 0;
  const items = [];
  const budgetViolations = [];
  let headerBody = `#pragma once
#include <Arduino.h>

typedef struct {
  const char* path;
  const uint8_t* data;
  const size_t len;
  const char* contentType;
  const char* contentEncoding;
} GzAsset;

`;

  for (const fname of files) {
    const inPath = path.join(WEB_DIR, fname);
    const raw = await fs.readFile(inPath, "utf8");
    const origSize = Buffer.byteLength(raw, "utf8");

    const minified = await minify(raw, MINIFY_OPTIONS);
    const gz = zlib.gzipSync(Buffer.from(minified, "utf8"), { level: 9 });
    const gzSize = gz.length;

    totalOrig += origSize;
    totalGz += gzSize;

    const budget = GZ_SIZE_BUDGETS[fname];
    let budgetNote;
    if (budget === undefined) {
      budgetNote = "NO BUDGET DECLARED (add one to GZ_SIZE_BUDGETS)";
      budgetViolations.push(`${fname}: no gzip budget declared — add an entry to GZ_SIZE_BUDGETS in compress_htmls.mjs`);
    } else if (gzSize > budget) {
      budgetNote = `OVER BUDGET (${gzSize} > ${budget})`;
      budgetViolations.push(`${fname}: gzipped ${gzSize} bytes exceeds budget ${budget} bytes (+${gzSize - budget})`);
    } else {
      budgetNote = `within budget (${gzSize}/${budget}, ${budget - gzSize} to spare)`;
    }

    console.log(`Processing ${fname}...`);
    console.log(`  -> Original: ${origSize} bytes | Compressed: ${gzSize} bytes | ${budgetNote}`);

    const ident = toCIdent(path.basename(fname, ".html")) + "_html_gz";
    const keyPath = toPathKey(fname);

    headerBody += `
// ${fname} (minified+gz, ${gz.length} bytes)
const uint8_t ${ident}[] PROGMEM = {
  ${chunkBytes([...gz])}
};
const size_t ${ident}_len = ${gz.length};

`;

    items.push({ path: keyPath, ident, lenIdent: `${ident}_len` });
  }

  // output asset
  /*headerBody += `\nstatic const GzAsset HTML_ASSETS[] PROGMEM = {\n`;
  for (const it of items) {
    headerBody += `  { "${it.path}", ${it.ident}, ${it.lenIdent}, "text/html; charset=utf-8", "gzip" },\n`;
  }
  headerBody += `};\n\n`;
  headerBody += `static const size_t HTML_ASSETS_COUNT = ${items.length};\n`;*/

  await fs.mkdir(path.dirname(OUT_H), { recursive: true });
  await fs.writeFile(OUT_H, headerBody, "utf8");

  console.log("\n--------------------------------------------------");
  console.log("Summary:");
  console.log(`Processed ${files.length} files.`);
  console.log(`Total original size: ${totalOrig} bytes`);
  console.log(`Total compressed size: ${totalGz} bytes`);
  const savings = totalOrig > 0 ? (100 * (1 - totalGz / totalOrig)).toFixed(2) : "0.00";
  console.log(`Total flash memory savings: ${savings}%`);

  // Gzip size-regression gate: fail the build (and thus the PlatformIO prebuild) on any breach.
  if (budgetViolations.length) {
    console.error("\n--------------------------------------------------");
    console.error(`HTML gzip size gate FAILED (${budgetViolations.length} issue(s)):`);
    for (const v of budgetViolations) console.error(`  - ${v}`);
    console.error("Reduce the page or, if the growth is intended, raise the budget in compress_htmls.mjs (with review).");
    console.error("--------------------------------------------------");
    process.exit(1);
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
