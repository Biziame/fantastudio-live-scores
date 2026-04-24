const puppeteer = require('puppeteer');

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command) {
    console.error("Usage: node fetch_sofascore.js <date|incidents|lineups> [id]");
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();

    if (command === 'date') {
      const date = args[1];
      if (!date) {
        console.error("Usage: node fetch_sofascore.js date YYYY-MM-DD");
        process.exit(1);
      }

      const [year, month, day] = date.split('-');
      let found = false;

      await page.setRequestInterception(true);
      page.on('request', (request) => {
        request.continue();
      });

      page.on('response', async (response) => {
        if (found) return;
        const url = response.url();
        if (url.includes(`scheduled-events/${date}`)) {
          try {
            const buffer = await response.buffer();
            const json = JSON.parse(buffer.toString());
            console.log(JSON.stringify(json));
            found = true;
          } catch (e) {
            // ignore
          }
        }
      });

      await page.goto(`https://www.sofascore.com/football/${year}/${month}/${day}`, {
        waitUntil: 'networkidle0',
        timeout: 30000
      });

      await page.waitForFunction(() => found, { timeout: 30000 });

    } else if (command === 'incidents') {
      const sofascoreId = args[1];
      if (!sofascoreId) {
        console.error("Usage: node fetch_sofascore.js incidents <sofascore_id>");
        process.exit(1);
      }

      const url = `https://api.sofascore.com/api/v1/event/${sofascoreId}/incidents`;
      let found = false;

      await page.setRequestInterception(true);
      page.on('request', (request) => {
        request.continue();
      });

      page.on('response', async (response) => {
        if (found) return;
        const resUrl = response.url();
        if (resUrl.includes(`/event/${sofascoreId}/incidents`)) {
          try {
            const buffer = await response.buffer();
            const json = JSON.parse(buffer.toString());
            console.log(JSON.stringify(json));
            found = true;
          } catch (e) {
            // ignore
          }
        }
      });

      await page.goto(`https://www.sofascore.com/event/${sofascoreId}`, {
        waitUntil: 'networkidle0',
        timeout: 30000
      });

      await page.waitForFunction(() => found, { timeout: 30000 });

    } else if (command === 'lineups') {
      const sofascoreId = args[1];
      if (!sofascoreId) {
        console.error("Usage: node fetch_sofascore.js lineups <sofascore_id>");
        process.exit(1);
      }

      const url = `https://api.sofascore.com/api/v1/event/${sofascoreId}/lineups`;
      let found = false;

      await page.setRequestInterception(true);
      page.on('request', (request) => {
        request.continue();
      });

      page.on('response', async (response) => {
        if (found) return;
        const resUrl = response.url();
        if (resUrl.includes(`/event/${sofascoreId}/lineups`)) {
          try {
            const buffer = await response.buffer();
            const json = JSON.parse(buffer.toString());
            console.log(JSON.stringify(json));
            found = true;
          } catch (e) {
            // ignore
          }
        }
      });

      await page.goto(`https://www.sofascore.com/event/${sofascoreId}`, {
        waitUntil: 'networkidle0',
        timeout: 30000
      });

      await page.waitForFunction(() => found, { timeout: 30000 });

    } else {
      console.error("Unknown command. Use: date, incidents, or lineups");
      process.exit(1);
    }

  } finally {
    await browser.close();
  }
}

main();