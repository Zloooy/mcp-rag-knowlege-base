/*
 * SCP Foundation Slot Machine
 * A simple 3-reel, 3-row slot game with SCP-themed symbols.
 * Run in Node.js (no external dependencies). Uses the built-in readline module.
 *
 * How to run:
 *   1. Save this file as scp-slots.ts
 *   2. Compile: npx tsc scp-slots.ts --target es2020 --module commonjs
 *   3. Run:     node scp-slots.js
 *   (Or use ts-node: npx ts-node scp-slots.ts)
 *
 * Game rules:
 *   - You start with 100 credits.
 *   - Choose a bet amount before each spin.
 *   - Three reels spin and stop to form a 3x3 grid.
 *   - Only the centre row is a payline. If all three symbols on the centre row
 *     match, you win the bet multiplied by that symbol's payout.
 *   - The game ends when you run out of credits or choose to quit.
 */

import * as readline from 'readline';

// --------------------------------------------------------------------------
// Type definitions
// --------------------------------------------------------------------------
interface Symbol {
  name: string;        // SCP designation
  display: string;     // short text shown on the reels
  payout: number;      // multiplier for 3-of-a-kind on the payline
}

// --------------------------------------------------------------------------
// Game content: symbols, reel strip
// --------------------------------------------------------------------------
const SYMBOLS: Symbol[] = [
  { name: 'SCP-173',  display: '173', payout: 50 },
  { name: 'SCP-682',  display: '682', payout: 30 },
  { name: 'SCP-049',  display: '049', payout: 20 },
  { name: 'SCP-999',  display: '999', payout: 15 },
  { name: 'SCP-096',  display: '096', payout: 10 },
  { name: 'SCP-106',  display: '106', payout:  5 },
  { name: 'D-Class',  display: 'D-C', payout:  2 },
  { name: 'Researcher', display: 'Rsc', payout: 1 },
];

// Number of times each symbol appears on a single reel (total length 32).
const REEL_COUNTS = [1, 2, 3, 3, 4, 5, 7, 7]; // corresponds to SYMBOLS order

/**
 * Build a single reel strip by repeating each symbol according to REEL_COUNTS.
 */
function buildReelStrip(): Symbol[] {
  const strip: Symbol[] = [];
  SYMBOLS.forEach((sym, idx) => {
    for (let i = 0; i < REEL_COUNTS[idx]; i++) {
      strip.push(sym);
    }
  });
  return strip;
}

// --------------------------------------------------------------------------
// Reel class
// --------------------------------------------------------------------------
class Reel {
  private strip: Symbol[];
  private length: number;

  constructor() {
    this.strip = buildReelStrip();
    this.length = this.strip.length;
  }

  /**
   * Spin the reel: pick a random position (centre row).
   * Returns the three visible symbols (top, centre, bottom) with wrapping.
   */
  spin(): { top: Symbol; centre: Symbol; bottom: Symbol } {
    const pos = Math.floor(Math.random() * this.length);
    const top    = this.strip[(pos - 1 + this.length) % this.length];
    const centre = this.strip[pos];
    const bottom = this.strip[(pos + 1) % this.length];
    return { top, centre, bottom };
  }
}

// --------------------------------------------------------------------------
// Slot machine game
// --------------------------------------------------------------------------
class SCP_Slots {
  private credits: number;
  private bet: number;
  private reels: Reel[];
  private rl: readline.Interface;

  constructor() {
    this.credits = 100;
    this.bet = 0;
    this.reels = [new Reel(), new Reel(), new Reel()];
    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
  }

  /**
   * Main game loop (async).
   */
  async start(): Promise<void> {
    console.log('========================================');
    console.log('   SCP FOUNDATION SLOT MACHINE');
    console.log('========================================');
    console.log('Match 3 symbols on the centre row to win.');
    console.log('Credits: ' + this.credits);
    console.log('----------------------------------------');

    while (this.credits > 0) {
      const input = await this.ask('Enter bet (or "quit" to leave): ');
      if (input.toLowerCase() === 'quit') {
        break;
      }

      const betAmount = Number(input);
      if (isNaN(betAmount) || betAmount <= 0) {
        console.log('Invalid bet. Please enter a positive number.');
        continue;
      }
      if (betAmount > this.credits) {
        console.log(`Not enough credits. You have ${this.credits}.`);
        continue;
      }

      this.bet = betAmount;
      this.credits -= this.bet;

      // Spin the reels
      const grid = this.spinReels();
      const win = this.checkWin(grid);

      this.credits += win;
      this.displayGrid(grid, win);

      if (this.credits <= 0) {
        console.log('You are out of credits. Game over.');
        break;
      }
    }

    console.log(`Final credits: ${this.credits}. Thanks for playing!`);
    this.rl.close();
  }

  /**
   * Spin all reels and return a 3x3 grid: rows[0..2][col0..2].
   */
  private spinReels(): Symbol[][] {
    const results = this.reels.map(reel => reel.spin());
    // Build rows: top row (index 0), centre row (1), bottom row (2)
    const topRow    = results.map(r => r.top);
    const centreRow = results.map(r => r.centre);
    const bottomRow = results.map(r => r.bottom);
    return [topRow, centreRow, bottomRow];
  }

  /**
   * Check only the centre row for a win.
   * Returns the amount won (bet * symbol payout), or 0.
   */
  private checkWin(grid: Symbol[][]): number {
    const centre = grid[1]; // row index 1
    if (centre[0] === centre[1] && centre[1] === centre[2]) {
      return this.bet * centre[0].payout;
    }
    return 0;
  }

  /**
   * Display the grid and outcome.
   */
  private displayGrid(grid: Symbol[][], win: number): void {
    console.log('\n--- Spin Result ---');
    for (const row of grid) {
      const cells = row.map(s => `[ ${s.display.padEnd(4)} ]`).join(' ');
      console.log(cells);
    }
    console.log('--------------------');
    if (win > 0) {
      console.log(`WIN! +${win} credits (${grid[1][0].name} x3)`);
    } else {
      console.log('No win this time.');
    }
    console.log(`Credits: ${this.credits}\n`);
  }

  /**
   * Helper: promisify readline.question.
   */
  private ask(question: string): Promise<string> {
    return new Promise(resolve => this.rl.question(question, resolve));
  }
}

// --------------------------------------------------------------------------
// Entry point
// --------------------------------------------------------------------------
(async () => {
  const game = new SCP_Slots();
  await game.start();
})();