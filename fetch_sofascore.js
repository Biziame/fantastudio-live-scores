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

        const eventsData = await page.evaluate(() => {
          const events = [];
          const seenIds = new Set();
          const currentYear = new Date().getFullYear();
          let now = Math.floor(Date.now() / 1000);

          const anchors = document.querySelectorAll('a[href*="/event/"]');
          anchors.forEach((a) => {
            const href = a.getAttribute('href');
            const m = href?.match(/\/event\/(\d+)/);
            if (!m) return;

            const id = parseInt(m[1], 10);
            if (seenIds.has(id)) return;
            seenIds.add(id);

            let el = a;
            for (let i = 0; i < 10; i++) {
              if (!el) break;
              el = el.parentElement;
            }

            const txt = el?.textContent || '';

            const teams = txt.split(/vs|doppio|-/).map(s => s.trim()).filter(Boolean).slice(0, 2);
            const homeTeam = teams[0] || 'Home';
            const awayTeam = teams[1] || 'Away';

            let status = { code: 0, type: 'notstarted' };
            if (txt.toLowerCase().includes('live') || txt.toLowerCase().includes('in corso')) {
              status = { code: 2, type: 'inprogress' };
            } else if (txt.toLowerCase().includes('finished') || txt.toLowerCase().includes('terminato')) {
              status = { code: 3, type: 'finished' };
            }

            const score = txt.match(/(\d+)\s*-\s*(\d+)/);
            const homeScore = score ? parseInt(score[1], 10) : null;
            const awayScore = score ? parseInt(score[2], 10) : null;

            events.push({
              id: id,
              homeTeam: { name: homeTeam, id: null, nameCode: null },
              awayTeam: { name: awayTeam, id: null, nameCode: null },
              tournament: { name: 'Serie A', uniqueTournament: { id: 23 } },
              season: { year: currentYear },
              startTimestamp: now,
              homeScore: { current: homeScore, period1: null },
              awayScore: { current: awayScore, period1: null },
              status: status,
              roundInfo: { round: null },
            });
          });

          return { events };
        });

        console.error('DEBUG events found:', eventsData.events.length);

        if (eventsData.events.length === 0) {
          console.error('Nessun evento trovato nel DOM');
          process.exit(1);
        }

        console.log(JSON.stringify(eventsData));

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