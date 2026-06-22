import { chromium } from "../frontend/node_modules/@playwright/test/index.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const args = parseArgs(process.argv.slice(2));
const loginUrl = requireArg(args, "login-url");
const allowedHosts = requireArg(args, "allowed-hosts").split(",").map((host) => host.trim()).filter(Boolean);
const captureHosts = (args["capture-hosts"] || args["allowed-hosts"]).split(",").map((host) => host.trim()).filter(Boolean);
const observeHosts = (args["observe-hosts"] || args["capture-hosts"] || args["allowed-hosts"]).split(",").map((host) => host.trim()).filter(Boolean);
const requiredCookieNames = (args["required-cookie-names"] || "").split(",").map((name) => name.trim()).filter(Boolean);
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
  let captureRequested = false;
  while (Date.now() < deadline) {
    const autoCaptured = await captureIfReady(page, false);
    if (autoCaptured) {
      break;
    }
    if (await exists(signalFile)) {
      captureRequested = true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  if (!(await exists(resultFile))) {
    const cookies = await context.cookies();
    await writeResult({
      status: "failed",
      message: captureRequested
        ? cookieFailureMessage(cookies, captureHosts, requiredCookieNames)
        : "Login browser timed out before a signed-in site session was available."
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

async function captureIfReady(page, force) {
  const cookies = await context.cookies();
  const observedCookies = cookies.filter((cookie) => isAllowedCookie(cookie.domain, observeHosts));
  const scopedCookies = cookies.filter((cookie) => isAllowedCookie(cookie.domain, captureHosts));
  const hasRequiredCookie =
    requiredCookieNames.length === 0 ||
    observedCookies.some((cookie) => requiredCookieNames.includes(cookie.name));

  if (scopedCookies.length === 0 || !hasRequiredCookie) {
    if (force) {
      await writeResult({
        status: "failed",
        message: cookieFailureMessage(cookies, captureHosts, requiredCookieNames)
      });
    }
    return false;
  }

  if (!force) {
    await settleSiteSession(page);
  }
  const settledCookies = await context.cookies();
  const settledScopedCookies = settledCookies.filter((cookie) => isAllowedCookie(cookie.domain, captureHosts));

  await writeResult({
    status: "captured",
    cookie_header: settledScopedCookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; "),
    cookie_count: settledScopedCookies.length,
    cookie_names: settledScopedCookies.map((cookie) => cookie.name),
    cookie_domains: [...new Set(settledScopedCookies.map((cookie) => cookie.domain))]
  });
  return true;
}

async function settleSiteSession(page) {
  try {
    await page.goto(loginUrl, { waitUntil: "domcontentloaded", timeout: 15000 });
    await page.waitForTimeout(1500);
  } catch {
    await page.waitForTimeout(1500);
  }
}

function cookieFailureMessage(cookies, hosts, requiredNames) {
  const observedDomains = [...new Set(cookies.map((cookie) => cookie.domain.replace(/^\./, "").toLowerCase()))].sort();
  const observedNames = [...new Set(cookies.map((cookie) => cookie.name))].sort();
  if (observedDomains.length === 0) {
    return "No browser cookies were available. Complete the site login before capturing the session.";
  }
  const requiredNote = requiredNames.length > 0 ? ` Required cookie names: ${requiredNames.join(", ")}.` : "";
  return `No usable site session cookies were available for ${hosts.join(", ")}.${requiredNote} Observed cookie domains: ${observedDomains.join(", ")}. Observed cookie names: ${observedNames.join(", ")}.`;
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
