# March Madness Bracket Predictor

This tool predicts March Madness tournament outcomes using a blended ELO + advanced stats model with seed-calibrated randomness. It can scrape live data, pull historical results, and run thousands of simulations to produce win probabilities for every team.

## Features

- **Win probability model** — blends ELO ratings (65%) with KenPom-equivalent efficiency stats (35%) using a logistic curve calibrated to historical outcomes
- **Advanced stats (KenPom-equivalent)** — scrapes AdjOE, AdjDE, AdjT, and NetRtg from barttorvik.com flat-file endpoints (no JS rendering required)
- **Historical performance** — pulls actual NCAA tournament game results from sports-reference.com and computes upset rates by seed matchup and round
- **Monte Carlo simulations** — runs N simulations and outputs championship probabilities and round-reach probabilities for every team
- **ELO ratings** — scrapes live ELO from warrennolan.com
- **Tournament bracket** — scrapes seeds and regions from sports-reference.com, with First Four fallback detection
- Seed-calibrated multiplicative noise tuned to historical NCAA upset rates
- Top seeds become more dominant in later rounds (as in real tournaments); surviving Cinderella teams become more volatile
- Exports single-run bracket predictions and simulation probability results to JSON
- Organizes data by tournament year in separate directories
- Debug mode with verbose per-game probability breakdowns

## Requirements

- Python 3.11 (see `.python-version`)
- pyenv + a local `.venv` (see setup below)

## Installation

This repo uses pyenv to manage the Python version and a local `.venv` for dependencies.

### 1. Install the Python version

```bash
pyenv install 3.11
```

The `.python-version` file in the repo root will automatically activate Python 3.11 when you `cd` into the directory.

### 2. Create and activate the virtual environment

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify

```bash
python -c "import pandas; print('OK')"
```

> **Tip:** Add `.venv/` to your shell's cd-hook or use a tool like `direnv` to auto-activate the venv when you enter the project directory.

## Project Structure

```
march_madness/
├── index.py                          # Main entry point
├── bracket_predictor.py              # Core prediction engine
├── scrapers.py                       # Data scraping module
├── requirements.txt
├── .python-version                   # Pins Python 3.11 for pyenv
├── README.md
├── 2025/
│   ├── elo_ratings.csv               # ELO ratings
│   ├── tournament_teams.csv          # Seeds and regions
│   ├── advanced_stats.csv            # AdjOE/AdjDE/AdjT from barttorvik
│   ├── historical_results.csv        # Raw historical game outcomes
│   ├── historical_upset_rates.csv    # Aggregated upset rates by seed matchup
│   ├── predicted_bracket.json        # Single-run bracket prediction
│   └── simulation_probabilities.json # Win probabilities from N simulations
├── samples/
│   ├── sample_elo_ratings.csv
│   └── tournament_teams_2024.csv
└── debug/                            # Raw HTML and CSV debug output
```

## Usage

### Full pipeline (scrape everything + simulate)

```bash
python index.py --year 2026 \
    --scrape \
    --scrape-tournament \
    --scrape-advanced \
    --historical \
    --simulations 1000
```

This will:
1. Scrape ELO ratings from warrennolan.com
2. Scrape tournament seeds/regions from sports-reference.com
3. Scrape advanced stats (AdjOE/AdjDE/AdjT) from barttorvik.com
4. Pull historical tournament results (2010–present) and compute upset rates
5. Run 1000 simulations and print the top-10 championship probabilities
6. Save all outputs under `2026/`

### Scrape only ELO + tournament bracket

```bash
python index.py --year 2026 --scrape --scrape-tournament
```

### Add advanced stats to an existing prediction

```bash
python index.py --year 2026 --scrape-advanced
```

If `2026/advanced_stats.csv` already exists it will be loaded automatically without `--scrape-advanced`.

### Pull historical data only

```bash
python index.py --year 2026 --scrape --scrape-tournament --historical --historical-start 2010
```

Saves:
- `2026/historical_results.csv` — one row per game (Year, Round, seeds, winner, Upset flag)
- `2026/historical_upset_rates.csv` — upset rates by seed matchup × round

### Run simulations

```bash
python index.py --year 2026 --simulations 5000
```

Outputs `2026/simulation_probabilities.json` with:
- `champion_prob` — probability each team wins the title
- `round_reach_prob` — probability each team reaches each round

### Use pre-existing data files

```bash
python index.py --year 2026 \
    --elo 2026/elo_ratings.csv \
    --tournament 2026/tournament_teams.csv \
    --advanced-stats 2026/advanced_stats.csv \
    --simulations 1000
```

### Scrape data without running a prediction

```bash
python scrapers.py --year 2026 --type both
```

Options: `--type elo`, `--type tournament`, `--type both`

### Debug mode

```bash
python index.py --year 2026 --scrape --scrape-tournament --scrape-advanced --debug
```

Saves raw HTML and intermediate CSVs to `debug/`. In single-bracket mode, also prints a per-game probability breakdown (ELO component, efficiency component, blended probability, noise factor, and upset flag) for every matchup.

## How the Model Works

### Win Probability

For each matchup, team1's win probability is computed as:

```
p_elo  = 1 / (1 + 10^(-(elo1 - elo2) / 400))          # standard ELO formula
p_eff  = 1 / (1 + exp(-0.15 * (netRtg1 - netRtg2)))    # efficiency logistic model
p_win  = 0.65 * p_elo + 0.35 * p_eff                   # blend (when adv stats available)
```

The logistic scale (k=0.15) is calibrated so a +10 net-rating advantage ≈ 75% win probability, consistent with KenPom historical data. ELO is weighted more heavily (65%) because it is purpose-built for tournament seeding and historically well-calibrated; advanced stats serve as a secondary signal.

### Seed-Calibrated Noise

Simulation outcomes use a **multiplicative noise** model. A composite strength score is built for each team (ELO + net_rtg scaled to ELO units at 65/35 weighting), and independent random multipliers are applied to each team's score before comparing them. This means a tiny noise factor on a large ELO gap produces near-zero upset probability, while a large factor on an even matchup creates a near coin-flip — naturally matching historical upset rates without clamping.

**First round noise** is calibrated directly to historical upset rates:

| Matchup | Historical upset rate | Noise factor |
|---------|----------------------|--------------|
| 1 vs 16 | ~1.3% | ±3% |
| 2 vs 15 | ~7.1% | ±10% |
| 3 vs 14 | ~14.7% | ±15% |
| 4 vs 13 | ~20.5% | ±18% |
| 5 vs 12 | ~35.3% | ±27% |
| 6 vs 11 | ~39.1% | ±30% |
| 7 vs 10 | ~38.7% | ±30% |
| 8 vs 9  | ~51.9% | ±40% |

**In later rounds**, noise is seed-dependent:
- **#1 seeds**: noise decreases each round (floor ±5%) — reflecting their 79%+ Sweet 16 win rate
- **#2–#4 seeds**: noise also decreases, but more gradually
- **#5–#8 seeds**: slight decrease
- **#9–#16 seeds (Cinderella runs)**: noise *increases* each round — these teams are genuinely volatile, but their lower composite strength still gates upset probability

#1 seeds also receive a +5% composite strength boost in the Championship game (64.1% historical title win rate).

### Monte Carlo Simulations

`--simulations N` reruns the full tournament N times independently. Output includes:
- Championship win probability per team
- Probability of reaching each round (First Round → Championship)

## Data Sources

| Data | Source | CLI flag |
|------|--------|----------|
| ELO ratings | warrennolan.com | `--scrape` |
| Tournament seeds/regions | sports-reference.com | `--scrape-tournament` |
| Advanced stats (AdjOE/AdjDE/AdjT) | barttorvik.com (flat-file CSV + JSON API fallbacks) | `--scrape-advanced` |
| Historical game results | sports-reference.com | `--historical` |

> **Note on barttorvik scraping:** The scraper uses barttorvik's flat-file endpoints (`{year}_team_results.csv`) which don't require JavaScript rendering. It falls back to the `teamslicejson.php` JSON API and then `trank.php?json=1` if the primary endpoint is unavailable.

## Data Formats

### Advanced Stats CSV (`advanced_stats.csv`)
| Column | Description |
|--------|-------------|
| `Team` | Team name |
| `AdjOE` | Adjusted offensive efficiency (points per 100 possessions) |
| `AdjDE` | Adjusted defensive efficiency (points allowed per 100) |
| `AdjT` | Adjusted tempo (possessions per 40 minutes) |
| `NetRtg` | Net rating = AdjOE − AdjDE |
| `TRank` | T-Rank overall ranking |

### Simulation Probabilities JSON (`simulation_probabilities.json`)
```json
{
  "simulations": 1000,
  "champion_prob": {
    "Duke": 0.142,
    "Kansas": 0.118,
    ...
  },
  "round_reach_prob": {
    "Sweet 16": { "Duke": 0.81, ... },
    "Elite Eight": { "Duke": 0.61, ... },
    ...
  }
}
```

### Predicted Bracket JSON (`predicted_bracket.json`)
```json
{
  "First Round": [
    {
      "game_id": 1,
      "unique_game_id": 1,
      "team1": "1. Duke",
      "team2": "16. Norfolk State",
      "winner": "1. Duke",
      "region": "East"
    }
  ]
}
```

## Sample Files

The `samples/` directory contains reference files:
- `sample_elo_ratings.csv` — example ELO ratings format
- `tournament_teams_2024.csv` — example tournament team format from 2024
