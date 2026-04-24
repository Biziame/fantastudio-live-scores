import puppeteer from 'puppeteer';

async function main() {
  try {
    const args = process.argv.slice(2);
    const command = args[0];

    if (!command) {
      console.error('Usage: node fetch_sofascore.js <date|incidents|lineups> [id]');
      process.exit(1);
    }

    const browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
      ],
    });

    try {
      const page = await browser.newPage();
      await page.setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
      );
      await page.setExtraHTTPHeaders({ 'Accept-Language': 'it-IT,it;q=0.9' });

      if (command === 'date') {
        const date = args[1];
        if (!date) {
          console.error('Usage: node fetch_sofascore.js date YYYY-MM-DD');
          process.exit(1);
        }

        let result = null;

        page.on('response', async (response) => {
          const url = response.url();

          if (url.includes('api.sofascore')) {
            console.error('DEBUG api.sofascore URL:', url);
          }

          if (result) return;
          if (url.includes('scheduled-events')) {
            try {
              const buffer = await response.buffer();
              const text = buffer.toString();

              console.error('DEBUG scheduled-events response length:', text.length);

              const json = JSON.parse(text);
              result = json;
            } catch (err) {
              console.error('DEBUG parse error on scheduled-events:', err?.message || err);
            }
          }
        });

        await page.goto(`https://www.sofascore.com/football/${date}`, {
          waitUntil: 'networkidle0',
          timeout: 45000,
        });

        if (!result) {
          await new Promise((r) => setTimeout(r, 5000));
        }

        if (!result) {
          console.error('Nessuna risposta intercettata');
          process.exit(1);
        }

        console.log(JSON.stringify(result));

      } else if (command === 'incidents') {
        const id = args[1];
        let result = null;
        page.on('response', async (res) => {
          if (result || !res.url().includes(`/event/${id}/incidents`)) return;
          try { result = JSON.parse((await res.buffer()).toString()); } catch (_) {}
        });
        await page.goto(`https://www.sofascore.com/event/${id}`, { waitUntil: 'networkidle0', timeout: 45000 });
        if (!result) await new Promise((r) => setTimeout(r, 5000));
        if (!result) { console.error('Nessuna risposta intercettata'); process.exit(1); }
        console.log(JSON.stringify(result));

      } else if (command === 'lineups') {
        const id = args[1];
        let result = null;
        page.on('response', async (res) => {
          if (result || !res.url().includes(`/event/${id}/lineups`)) return;
          try { result = JSON.parse((await res.buffer()).toString()); } catch (_) {}
        });
        await page.goto(`https://www.sofascore.com/event/${id}`, { waitUntil: 'networkidle0', timeout: 45000 });
        if (!result) await new Promise((r) => setTimeout(r, 5000));
        if (!result) { console.error('Nessuna risposta intercettata'); process.exit(1); }
        console.log(JSON.stringify(result));
      }

    } finally {
      await browser.close();
    }
  } catch (e) {
    console.error('FATAL puppeteer error:', e?.message || e);
    process.exit(1);
  }
}

main();