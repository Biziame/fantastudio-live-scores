import puppeteer from 'puppeteer';

const command = process.argv[2];
const param   = process.argv[3];

if (!command || !param) {
  process.stderr.write('Usage: node fetch_sofascore.js <date|incidents|lineups> <value>\n');
  process.exit(1);
}

async function fetchSofascore() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const page = await browser.newPage();

  await page.setUserAgent(
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
  );

  try {
    let url;

    if (command === 'date') {
      url = `https://api.sofascore.com/api/v1/sport/football/scheduled-events/${param}`;
    } else if (command === 'incidents') {
      url = `https://api.sofascore.com/api/v1/event/${param}/incidents`;
    } else if (command === 'lineups') {
      url = `https://api.sofascore.com/api/v1/event/${param}/lineups`;
    } else {
      process.stderr.write(`Comando sconosciuto: ${command}\n`);
      process.exit(1);
    }

    process.stderr.write(`Fetching: ${url}\n`);

    const response = await page.goto(url, {
      waitUntil: 'networkidle0',
      timeout: 30000
    });

    const status = response.status();
    if (status !== 200) {
      process.stderr.write(`HTTP ${status}\n`);
      process.exit(1);
    }

    const json = await response.json();
    process.stdout.write(JSON.stringify(json) + '\n');

  } finally {
    await browser.close();
  }
}

fetchSofascore().catch(e => {
  process.stderr.write(e.message + '\n');
  process.exit(1);
});