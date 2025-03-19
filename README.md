# March Madness Bracket Predictor

This script predicts March Madness tournament outcomes using ELO ratings with historical upset patterns.

## Features

- Predicts winners based on ELO ratings with seed-calibrated randomness
- Randomness is tuned to match historical NCAA tournament outcomes
- Higher seeds become more dominant in later rounds (as in real tournaments)
- Allows manual input of team data or loading from files
- Simulates the entire tournament bracket
- Exports results to JSON for further analysis
- Scrapes the latest ELO ratings from warrennolan.com
- Scrapes tournament teams and brackets from sports-reference.com
- Handles incomplete tournament data with TBD placeholders
- Supports unique game IDs throughout the tournament
- Organizes data by tournament year in separate directories
- Includes debug mode for troubleshooting

## Requirements

- Python 3.6+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository
2. Set up a virtual environment:
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment (Linux/Mac)
   source venv/bin/activate
   
   # Activate virtual environment (Windows)
   venv\Scripts\activate
   ```
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Project Structure

```
march_madness/
├── index.py               # Main entry point
├── bracket_predictor.py   # Core prediction engine
├── scrapers.py            # Data scraping module (ELO & tournament)
├── requirements.txt       # Dependencies
├── README.md              # This file
├── 2025/                  # Year-specific tournament data
│   ├── elo_ratings.csv    # ELO ratings for 2025
│   ├── tournament_teams.csv # Tournament teams for 2025 
│   └── predicted_bracket.json # Prediction results for 2025
├── samples/               # Sample data files
│   ├── sample_elo_ratings.csv
│   └── tournament_teams_2024.csv
└── debug/                 # Debug output files
    ├── raw_elo_2025.csv            # Raw ELO data before processing
    ├── elo_page_2025.html          # Raw HTML from ELO scraping
    ├── raw_tournament_2025.csv     # Raw tournament team data
    └── tournament_page_2025.html   # Raw HTML from tournament scraping
```

## Files

- `bracket_predictor.py` - Core prediction engine and tournament simulation logic
- `scrapers.py` - Module for scraping data (ELO ratings and tournament teams)
- `index.py` - Main entry point with the handler function

## Usage

### Quick Prediction

The main way to use this tool is through the index.py file:

```
python index.py
```

By default, this will:
1. Use the current year (or next year if after June)
2. Look for files in a directory named with the year (e.g., "2025")
3. Create this directory if it doesn't exist

You can customize the prediction with command-line arguments:
```
python index.py --year 2025 --randomness 0.1
```

### Scraping Data

To scrape the latest ELO ratings from warrennolan.com:
```
python index.py --year 2025 --scrape
```

To scrape tournament teams from sports-reference.com:
```
python index.py --year 2025 --scrape-tournament
```

To scrape both ELO ratings and tournament teams in one command:
```
python index.py --year 2025 --scrape --scrape-tournament
```

### Working with Different Years

Specify a different tournament year:
```
python index.py --year 2024
```

All files will be organized in year-specific directories:
- `2025/elo_ratings.csv` - ELO ratings for 2025
- `2025/tournament_teams.csv` - Tournament teams for 2025
- `2025/predicted_bracket.json` - Prediction results for 2025

### Debug Mode

For troubleshooting or investigating issues, use the debug mode:
```
python index.py --year 2025 --scrape --scrape-tournament --debug
```

This will:
- Save raw HTML from scraping to debug files
- Save raw data before processing
- Print additional information during execution
- Show full error tracebacks if errors occur

### Interactive Mode

For an interactive experience, you can use the bracket_predictor.py directly:
```
python bracket_predictor.py
```

### Scraping Data Directly

To only scrape data without generating a prediction:
```
python scrapers.py --year 2025 --type elo
```

Or for tournament teams:
```
python scrapers.py --year 2025 --type tournament
```

Or both:
```
python scrapers.py --year 2025 --type both
```

To include debug information:
```
python scrapers.py --year 2025 --type both --debug
```

## Data Format

### ELO Ratings File (CSV)
Your ELO ratings CSV should have at minimum these columns:
- `Team`: Team name
- `ELO`: ELO rating

### Tournament Teams File (CSV)
The tournament teams file should have these columns:
- `Team`: Team name
- `Seed`: Seed number (1-16)
- `Region`: Region name (East, West, South, Midwest)

### Predicted Bracket JSON Format

The predicted bracket JSON file includes:
- Round-based organization (First Round, Second Round, etc.)
- Unique game IDs that remain consistent throughout the tournament
- Round-specific game IDs that restart at each round
- Teams, winners, and regions for each matchup

Example JSON structure:
```json
{
  "First Round": [
    {
      "game_id": 1,
      "unique_game_id": 1,
      "team1": "Team A",
      "team2": "Team B",
      "winner": "Team A",
      "region": "East"
    },
    // ...
  ],
  // Additional rounds...
}
```

## How Randomness Works

The bracket predictor uses a sophisticated seed-calibrated randomness approach based on historical NCAA tournament data:

### First Round Matchups
- 1 vs 16: 1.3% upset chance (~3% randomness factor)
- 2 vs 15: 7.1% upset chance (~10% randomness factor)
- 3 vs 14: 14.7% upset chance (~15% randomness factor)
- 4 vs 13: 20.5% upset chance (~18% randomness factor)
- 5 vs 12: 35.3% upset chance (~27% randomness factor)
- 6 vs 11: 39.1% upset chance (~30% randomness factor)
- 7 vs 10: 38.7% upset chance (~30% randomness factor)
- 8 vs 9: 51.9% upset chance (~40% randomness factor)

### Later Rounds
The model recognizes that higher seeds become more dominant in later rounds:

- #1 seeds: Randomness progressively decreases from 16% → 12% → 8% → 5%
- #2 seeds: Randomness decreases from 17% → 14% → 11% → 8%
- #3-4 seeds: Randomness decreases more gradually
- #5-8 seeds: Randomness decreases slightly
- #9-16 seeds: Randomness actually increases slightly

### Championship Boost
- #1 seeds receive a 5% boost in the championship game (reflecting their 64.1% championship win rate)

This approach produces realistic tournament outcomes where early rounds see frequent upsets (especially in 5-12, 6-11, and 7-10 matchups), but the later rounds tend to be dominated by higher seeds - just like in real NCAA tournaments.

The randomness is applied by adjusting each team's ELO rating up or down by a random percentage (within the range specified for that seed and round).

## Example

Without a tournament teams file, the script will:
1. Scrape or load ELO ratings
2. Automatically create a bracket based on ELO rankings
3. Assign seeds 1-16 to the top 64 teams across 4 regions

If you want to customize the tournament teams and their seeds:

1. Create a file named `[year]/tournament_teams.csv` (e.g., `2025/tournament_teams.csv`)
2. Include columns for Team, Seed, and Region
3. Run the prediction with: `python index.py --year 2025` 

Alternatively, you can scrape real tournament data automatically:
```
python index.py --year 2025 --scrape-tournament
```

For incomplete tournament data (such as TBD play-in games), the script will:
1. Create placeholder TBD teams
2. Simulate the tournament with the available teams
3. Maintain bracket integrity even with missing teams

## Sample Files

The `samples/` directory contains reference files:
- `sample_elo_ratings.csv` - Example of ELO ratings format
- `tournament_teams_2024.csv` - Example tournament team format from 2024

You can use these as templates for creating your own data files. 