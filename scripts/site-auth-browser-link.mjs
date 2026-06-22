import { chromium } from "../frontend/node_modules/@playwright/test/index.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const args = parseArgs(process.argv.slice(2));
const loginUrl = requireArg(args, "login-url");
const allowedHosts = requireArg(args, "allowed-hosts").split(",").map((host) => host.trim()).filter(Boolean);
const signalFile = requireArg(args, "signal-file");
const resultFile = requireArg(args, "result-file");
const timeoutSeconds = Number(args["timeout-seconds"] || "900");
const userDataDir = path.join(path.dirname(resultFile), "browser-profile");

await fs.mkdir(path.dirname(resultFile), { recursive: true });

let context;
try {
  context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    viewport: { width: 1280, height: 900 }
  });
  const page = context.pages()[0] || await context.newPage();
  await page.goto(loginUrl, { waitUntil: "domcontentloaded" });

  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    if (await exists(signalFile)) {
      const cookies = await context.cookies([
        loginUrl,
        ...allowedHosts.map((host) => `https://${host}/`)
      ]);
      const scopedCookies = cookies.filter((cookie) => isAllowedCookie(cookie.domain, allowedHosts));
      if (scopedCookies.length === 0) {
        await writeResult({
          status: "failed",
          message: "No site-scoped cookies were available from the login browser."
        });
        break;
      }
      await writeResult({
        status: "captured",
        cookie_header: scopedCookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; "),
        cookie_count: scopedCookies.length,
        cookie_names: scopedCookies.map((cookie) => cookie.name),
        cookie_domains: [...new Set(scopedCookies.map((cookie) => cookie.domain))]
      });
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  if (!(await exists(resultFile))) {
    await writeResult({
      status: "failed",
      message: "Login browser timed out before capture was requested."
    });
  }
} catch (error) {
  await writeResult({
    status: "failed",
    message: error instanceof Error ? error.message : "Login browser failed."
  });
} finally {
  if (context) {
    await context.close();
  }
}

function parseArgs(rawArgs) {
  const parsed = {};
  for (let index = 0; index < rawArgs.length; index += 2) {
    const key = rawArgs[index]?.replace(/^--/, "");
    if (!key) {
      continue;
    }
    parsed[key] = rawArgs[index + 1] || "";
  }
  return parsed;
}

function requireArg(parsed, key) {
  const value = parsed[key];
  if (!value) {
    throw new Error(`Missing required --${key}`);
  }
  return value;
}

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function writeResult(result) {
  const tmpFile = `${resultFile}.tmp`;
  await fs.writeFile(tmpFile, JSON.stringify(result, null, 2), { mode: 0o600 });
  await fs.rename(tmpFile, resultFile);
}

function isAllowedCookie(domain, hosts) {
  const normalizedDomain = domain.replace(/^\./, "").toLowerCase();
  return hosts.some((host) => normalizedDomain === host || normalizedDomain.endsWith(`.${host}`));
}
