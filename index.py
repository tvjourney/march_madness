#!/usr/bin/env python3
"""
March Madness Bracket Prediction - Main Entry Point

This script serves as the main entry point for the March Madness bracket predictor.
It provides a handler function that orchestrates the prediction process.
"""

import os
import argparse
import sys
from typing import Optional
import pandas as pd
import datetime

from bracket_predictor import BracketPredictor, Team, Matchup
from scrapers import scrape_elo_ratings, scrape_tournament_teams, add_tournament_info, ensure_dir_exists

def handler(
    year: Optional[int] = None,
    elo_file: Optional[str] = None, 
    tournament_file: Optional[str] = None,
    randomness: float = 0.1,
    scrape_elo: bool = False,
    scrape_tournament: bool = False,
    output_file: Optional[str] = None,
    debug: bool = False
) -> int:
    """
    Main handler function that orchestrates the bracket prediction process.
    
    Args:
        year: Tournament year (defaults to current year or next year if after June)
        elo_file: Path to ELO ratings CSV file, or None to use default
        tournament_file: Path to tournament teams CSV file, or None to use default
        randomness: Randomness factor (0-1) where 0 is pure ELO and 1 is pure random
        scrape_elo: Whether to scrape ELO from warrennolan.com
        scrape_tournament: Whether to scrape tournament data from sports-reference.com
        output_file: Path to save the bracket prediction JSON, or None to use default
        debug: Whether to output debug information
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Determine the year if not provided
        if year is None:
            current_year = datetime.datetime.now().year
            if datetime.datetime.now().month < 6:
                year = current_year
            else:
                year = current_year + 1
                
        print(f"Working with {year} tournament data")
        
        # Set up directory for the year
        year_dir = str(year)
        ensure_dir_exists(year_dir)
        
        # Set default file paths if not provided
        if elo_file is None:
            elo_file = os.path.join(year_dir, "elo_ratings.csv")
        
        if tournament_file is None:
            tournament_file = os.path.join(year_dir, "tournament_teams.csv")
            
        if output_file is None:
            output_file = os.path.join(year_dir, "predicted_bracket.json")
        
        # Step 1: Get ELO ratings
        elo_df = None
        if scrape_elo:
            print(f"Scraping ELO ratings from warrennolan.com for {year}...")
            elo_df = scrape_elo_ratings(year, debug=debug)
            if elo_df is not None:
                elo_df.to_csv(elo_file, index=False)
                print(f"Saved scraped ELO ratings to {elo_file}")
        elif os.path.exists(elo_file):
            print(f"Loading ELO ratings from {elo_file}")
            elo_df = pd.read_csv(elo_file)
        else:
            print(f"ELO ratings file {elo_file} not found. Please use --scrape to download it.")
            return 1
        
        if elo_df is None:
            print("Error: Could not get ELO ratings.")
            return 1
        
        # Step 2: Get tournament information
        tournament_df = None
        if scrape_tournament:
            print(f"Scraping tournament teams from sports-reference.com for {year}...")
            tournament_df = scrape_tournament_teams(year, debug=debug)
            if tournament_df is not None:
                tournament_df.to_csv(tournament_file, index=False)
                print(f"Saved scraped tournament teams to {tournament_file}")
        elif os.path.exists(tournament_file):
            print(f"Loading tournament teams from {tournament_file}")
            tournament_df = pd.read_csv(tournament_file)
        
        # Step 3: Add tournament information to ELO ratings
        if tournament_df is not None or os.path.exists(tournament_file):
            if tournament_df is None:
                tournament_df = pd.read_csv(tournament_file)
            
            print(f"Tournament teams data contains {len(tournament_df)} teams")
            
            # Verify we have a complete tournament (64 teams, 4 regions, seeds 1-16 in each region)
            if len(tournament_df) < 64:
                print(f"Warning: Tournament data has only {len(tournament_df)} teams. A complete tournament should have 64 teams.")
            
            # Check that we have required columns
            required_columns = ['Team', 'Seed', 'Region']
            if not all(col in tournament_df.columns for col in required_columns):
                missing_cols = [col for col in required_columns if col not in tournament_df.columns]
                print(f"Warning: Tournament data is missing columns: {', '.join(missing_cols)}")
                return 1
            
            # Check for a complete set of regions
            regions = tournament_df['Region'].unique()
            if len(regions) != 4:
                print(f"Warning: Found {len(regions)} regions, but expected 4 (East, West, South, Midwest). Regions: {', '.join(regions)}")
            
            # Check if each region has a complete set of seeds (1-16)
            for region in regions:
                region_df = tournament_df[tournament_df['Region'] == region]
                seeds = set(region_df['Seed'])
                missing_seeds = [seed for seed in range(1, 17) if seed not in seeds]
                if missing_seeds:
                    print(f"Warning: Region {region} is missing seeds: {', '.join(str(s) for s in missing_seeds)}")
            
            # Merge tournament data with ELO ratings
            print(f"Adding tournament information from {tournament_file}")
            combined_df = add_tournament_info(elo_df, tournament_file, debug)
            
            # Count teams with complete info
            complete_teams = combined_df.dropna(subset=['Seed', 'Region'])
            print(f"Found {len(complete_teams)} teams in the tournament")
            
            # Check if any tournament teams don't have ELO ratings
            tournament_teams_without_elo = tournament_df[~tournament_df['Team'].isin(elo_df['Team'])]
            if not tournament_teams_without_elo.empty:
                print(f"Warning: {len(tournament_teams_without_elo)} tournament teams don't have ELO ratings:")
                for _, row in tournament_teams_without_elo.iterrows():
                    print(f"  - {row['Team']} (Seed: {row['Seed']}, Region: {row['Region']})")
                
                # Add missing teams with a default ELO
                default_elo = elo_df['ELO'].median()
                print(f"Adding missing teams with default ELO rating of {default_elo:.2f}")
                
                for _, row in tournament_teams_without_elo.iterrows():
                    new_row = {'Team': row['Team'], 'ELO': default_elo, 'Seed': row['Seed'], 'Region': row['Region']}
                    combined_df = pd.concat([combined_df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            print(f"Tournament teams file {tournament_file} not found.")
            print("Will use all teams from ELO ratings. Please create a tournament file for more accurate predictions.")
            combined_df = elo_df
            # Try to add some placeholder information for a basic simulation
            if 'Seed' not in combined_df.columns or combined_df['Seed'].isna().all():
                print("Adding placeholder seeds based on ELO ranking")
                # Sort by ELO descending
                sorted_df = combined_df.sort_values(by='ELO', ascending=False)
                # Assign seeds 1-16 to top 64 teams across 4 regions
                seeds = []
                regions = ['East', 'West', 'South', 'Midwest']
                for i in range(min(len(sorted_df), 64)):
                    seed = (i % 16) + 1
                    region = regions[i // 16]
                    seeds.append({'Seed': seed, 'Region': region})
                
                # Pad with None values if fewer than 64 teams
                while len(seeds) < len(sorted_df):
                    seeds.append({'Seed': None, 'Region': None})
                
                # Update DataFrame
                seed_df = pd.DataFrame(seeds)
                combined_df = pd.concat([sorted_df.reset_index(drop=True), seed_df.reset_index(drop=True)], axis=1)
        
        # Step 4: Prepare data for the predictor
        teams_data = []
        for _, row in combined_df.iterrows():
            # Only include teams with seed and region information
            if pd.notna(row.get('Seed')) and pd.notna(row.get('Region')):
                team_data = {
                    "name": row["Team"],
                    "seed": int(row["Seed"]),
                    "region": row["Region"],
                    "elo": float(row["ELO"])
                }
                teams_data.append(team_data)
        
        if not teams_data:
            print("Error: No teams found with complete tournament information.")
            return 1
        
        # Check if we have a complete tournament
        if len(teams_data) < 64:
            print(f"Warning: Only {len(teams_data)} teams found with complete information. A standard tournament requires 64 teams.")
        
        # Step 5: Run the prediction
        print(f"Predicting bracket with randomness factor: {randomness}")
        predictor = BracketPredictor(randomness_factor=randomness)
        predictor.setup_first_round(teams_data)
        results = predictor.simulate_tournament()
        
        # Step 6: Output results
        predictor.print_bracket(results)
        
        if output_file:
            predictor.export_bracket(results, output_file)
            print(f"Bracket prediction saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error in bracket prediction: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="March Madness bracket prediction")
    parser.add_argument("--year", type=int, default=None,
                        help="Tournament year (defaults to current year or next year if after June)")
    parser.add_argument("--elo", default=None, 
                        help="Path to ELO ratings CSV file")
    parser.add_argument("--tournament", default=None,
                        help="Path to tournament teams CSV file")
    parser.add_argument("--randomness", type=float, default=0.1,
                        help="Randomness factor (0-1)")
    parser.add_argument("--scrape", action="store_true",
                        help="Scrape ELO ratings from warrennolan.com")
    parser.add_argument("--scrape-tournament", action="store_true",
                        help="Scrape tournament data from sports-reference.com")
    parser.add_argument("--output", default=None,
                        help="Output JSON file for bracket prediction")
    parser.add_argument("--debug", action="store_true",
                        help="Show additional debug information")
    
    args = parser.parse_args()
    
    # Call the handler with parsed arguments
    sys.exit(handler(
        year=args.year,
        elo_file=args.elo,
        tournament_file=args.tournament,
        randomness=args.randomness,
        scrape_elo=args.scrape,
        scrape_tournament=args.scrape_tournament,
        output_file=args.output,
        debug=args.debug
    )) 