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
        if (!date) {
          console.error('Usage: node fetch_sofascore.js date YYYY-MM-DD');
          process.exit(1);
        }

        await page.goto(`https://www.sofascore.com/football/${date}`, {
          waitUntil: 'networkidle0',
          timeout: 45000,
        });

        await new Promise((r) => setTimeout(r, 3000));

        const data = await page.evaluate((dateStr) => {
          const events = [];

          const links = Array.from(document.querySelectorAll('a[href*="#id:"]'));

          links.forEach((link) => {
            try {
              const href = link.getAttribute('href') || '';
              const m = href.match(/#id:(\d+)/);
              if (!m) return;
              const id = Number(m[1]);

              const raw = link.textContent.replace(/\s+/g, ' ').trim();
              if (!raw) return;
              const parts = raw.split(' ').filter(Boolean);

              const homeName = parts[0];
              const awayName = parts[parts.length - 1];

              let timeMatch = raw.match(/(\d{1,2}:\d{2})/);
              let startTimestamp;
              if (timeMatch) {
                const time = timeMatch[1];
                const [hh, mm] = time.split(':').map(Number);
                const dt = new Date(dateStr + 'T' + String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0') + ':00Z');
                startTimestamp = Math.floor(dt.getTime() / 1000);
              } else {
                startTimestamp = Math.floor(new Date(dateStr + 'T00:00:00Z').getTime() / 1000);
              }

              let tournamentName = '';
              let tournamentId = 23;
              let parent = link.parentElement;
              for (let i = 0; i < 5 && parent; i++) {
                const tLink = parent.querySelector('a[href*="/football/tournament/"]');
                if (tLink) {
                  tournamentName = tLink.textContent.replace(/\s+/g, ' ').trim();
                  const tHref = tLink.getAttribute('href') || '';
                  const tIdMatch = tHref.match(/\/tournament\/[^/]+\/[^/]+\/(\d+)/);
                  if (tIdMatch) {
                    tournamentId = Number(tIdMatch[1]);
                  }
                  break;
                }
                parent = parent.parentElement;
              }

              events.push({
                id,
                homeTeam: { name: homeName, id: null, nameCode: null },
                awayTeam: { name: awayName, id: null, nameCode: null },
                tournament: {
                  name: tournamentName,
                  uniqueTournament: { id: tournamentId },
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

        if (!data || !Array.isArray(data.events) || data.events.length === 0) {
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