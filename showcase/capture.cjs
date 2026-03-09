const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  // Go to the local dev server
  await page.goto('http://localhost:5173');

  // Wait for initial render and animations
  await page.waitForTimeout(2000);

  // Click the simulation button
  await page.click('button:has-text("Simulate E2EE Transport")');

  // Wait for the encrypted text to appear in the DOM
  await page.waitForTimeout(1000);

  // Take screenshot
  await page.screenshot({ path: '/Users/aniruddhakadam/.gemini/antigravity/brain/efdd17c9-6f94-462e-92a1-86d61f90020e/sdk_showcase_preview.png' });

  await browser.close();
})();
