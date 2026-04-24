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

      if (command === 'date') {
        const date = args[1];
        if (date !== '2026-04-24') {
          console.error('DEBUG: skip date', date);
          process.exit(0);
        }
        if (!date) {
          console.error('Usage: node fetch_sofascore.js date YYYY-MM-DD');
          process.exit(1);
        }

        await page.goto(`https://www.sofascore.com/football/${date}`, {
          waitUntil: 'networkidle0',
          timeout: 45000,
        });

        await new Promise((r) => setTimeout(r, 2000));

        const htmlSnippet = await page.evaluate(() => {
          return document.documentElement.innerHTML.slice(0, 5000);
        });
        console.error('DEBUG HTML SNIPPET:', htmlSnippet);

        const data = await page.evaluate((dateStr) => {
          const events = [];

          const links = Array.from(document.querySelectorAll('a[data-id][href*="#id:"]'));

          links.forEach((link) => {
            try {
              const idAttr = link.getAttribute('data-id');
              if (!idAttr) return;
              const id = Number(idAttr);

              const timeBdi = link.querySelector('bdi.textStyle_body\\.small');
              let time = timeBdi ? timeBdi.textContent.trim() : null;

              const teamBdis = link.querySelectorAll('bdi.textStyle_body\\.medium');
              if (teamBdis.length < 2) return;
              const homeName = teamBdis[0].textContent.trim();
              const awayName = teamBdis[1].textContent.trim();

              let startTimestamp;
              if (time && /^\d{1,2}:\d{2}$/.test(time)) {
                const [hh, mm] = time.split(':').map(Number);
                const dt = new Date(dateStr + 'T' + String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0') + ':00Z');
                startTimestamp = Math.floor(dt.getTime() / 1000);
              } else {
                startTimestamp = Math.floor(new Date(dateStr + 'T00:00:00Z').getTime() / 1000);
              }

              events.push({
                id,
                homeTeam: { name: homeName, id: null, nameCode: null },
                awayTeam: { name: awayName, id: null, nameCode: null },
                tournament: {
                  name: '',
                  uniqueTournament: { id: null },
                },
                season: { year: new Date(dateStr).getFullYear() },
                startTimestamp,
                homeScore: {},
                awayScore: {},
                status: { code: 0, type: 'notstarted' },
                roundInfo: {},
              });
            } catch (e) {}
          });

          console.error('DEBUG events found:', events.length);
          return { events };
        }, date);

        if (!data || !data.events || data.events.length === 0) {
          console.error('Nessun evento trovato nel DOM');
          process.exit(1);
        }

        console.log(JSON.stringify(data));

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