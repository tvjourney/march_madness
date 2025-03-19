#!/usr/bin/env python3
"""
Data Scrapers for March Madness

This module contains functions to scrape various data sources for March Madness information:
- ELO ratings from warrennolan.com
- Tournament brackets from sports-reference.com
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
import argparse
import os
import sys
import datetime
import re

def scrape_elo_ratings(year: Optional[int] = None, url: Optional[str] = None, debug: bool = False) -> Optional[pd.DataFrame]:
    """
    Scrape ELO ratings from Warren Nolan's website.
    
    Args:
        year: The year to scrape ELO ratings for. Defaults to current year.
        url: Override URL of the ELO ratings page. If None, constructs URL based on year.
        debug: Whether to save debug files
        
    Returns:
        DataFrame containing the ELO ratings or None if scraping failed
    """
    # Determine the year if not provided
    if year is None:
        current_year = datetime.datetime.now().year
        # If we're in the first few months of the year, we probably want last year's tournament
        if datetime.datetime.now().month < 6:
            year = current_year
        else:
            year = current_year + 1
    
    # Construct the URL if not provided
    if url is None:
        url = f"https://www.warrennolan.com/basketball/{year}/elo"
    
    try:
        print(f"Fetching ELO ratings from {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Save HTML to file for debugging
        if debug:
            ensure_dir_exists("debug")
            debug_html = os.path.join("debug", f"elo_page_{year}.html")
            with open(debug_html, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"Saved HTML to {debug_html} for debugging")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the stats table
        table = soup.find('table', {'class': 'stats-table'})
        
        if not table:
            print("Error: Could not find the stats-table")
            # Try any table
            table = soup.find('table')
            
        if not table:
            print("Error: Could not find any table")
            return None
        
        # Parse the table rows
        data = []
        
        # Skip the header row
        for row in table.find_all('tr')[1:]:
            cells = row.find_all('td')
            if not cells or len(cells) < 4:  # Need at least team, record, ELO, rank
                continue
            
            # Get team name
            team_cell = cells[0]
            team_name = None
            
            # Find the team name in the nested div structure
            name_container = team_cell.find('div', {'class': 'name-subcontainer'})
            if name_container:
                team_link = name_container.find('a')
                if team_link:
                    team_name = team_link.text.strip()
            
            # If not found in the nested structure, try alternative approaches
            if not team_name:
                # Try direct link
                team_link = team_cell.find('a')
                if team_link:
                    team_name = team_link.text.strip()
                else:
                    # Last resort: get all text
                    team_name = team_cell.text.strip()
            
            if not team_name:
                print("Warning: Could not extract team name from row")
                continue
            
            # Get record from second cell
            record = cells[1].text.strip() if len(cells) > 1 else ""
            
            # Get ELO from third cell
            elo_text = cells[2].text.strip() if len(cells) > 2 else ""
            try:
                elo = float(elo_text.replace(',', ''))
            except ValueError:
                print(f"Warning: Could not convert ELO value '{elo_text}' to float for team {team_name}")
                continue
            
            # Get rank from fourth cell
            rank = cells[3].text.strip() if len(cells) > 3 else ""
            
            # Get delta from fifth cell if it exists
            delta = cells[4].text.strip() if len(cells) > 4 else ""
            
            data.append({
                'Team': team_name,
                'Record': record,
                'ELO': elo,
                'Rank': rank,
                'ELO_Delta': delta,
                'Seed': None,
                'Region': None
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        print(f"Successfully scraped {len(df)} team ratings")
        
        # Save the raw data for debugging
        if debug:
            ensure_dir_exists("debug")
            raw_csv = os.path.join("debug", f"raw_elo_{year}.csv")
            df.to_csv(raw_csv, index=False)
            print(f"Saved raw data to {raw_csv} for debugging")
        
        return df
        
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        return None

def scrape_tournament_teams(year: Optional[int] = None, url: Optional[str] = None, debug: bool = False) -> Optional[pd.DataFrame]:
    """
    Scrape NCAA tournament team information from Sports Reference.
    
    Args:
        year: The year to scrape tournament data for. Defaults to current year.
        url: Override URL of the tournament page. If None, constructs URL based on year.
        debug: Whether to save debug files
        
    Returns:
        DataFrame containing tournament team information or None if scraping failed
    """
    # Determine the year if not provided
    if year is None:
        current_year = datetime.datetime.now().year
        # If we're in the first few months of the year, we probably want last year's tournament
        if datetime.datetime.now().month < 6:
            year = current_year
        else:
            year = current_year + 1
    
    # Construct the URL if not provided
    if url is None:
        url = f"https://www.sports-reference.com/cbb/postseason/men/{year}-ncaa.html"
    
    try:
        print(f"Fetching tournament data from {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Save HTML to file for debugging
        if debug:
            ensure_dir_exists("debug")
            debug_html = os.path.join("debug", f"tournament_page_{year}.html")
            with open(debug_html, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"Saved HTML to {debug_html} for debugging")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract tournament teams from all regions
        tournament_teams = []
        
        # Look for each region's section in the HTML
        region_divs = {}
        
        # Find divs with region IDs
        for region_name in ['east', 'west', 'south', 'midwest']:
            region_div = soup.find('div', {'id': region_name})
            if region_div:
                region_divs[region_name.capitalize()] = region_div
                if debug:
                    print(f"Found {region_name.capitalize()} region div")
        
        # If no divs with IDs found, try using HTML parsing based on strong tags with "First Four" in them
        if not region_divs:
            regions_to_find = ['East', 'West', 'South', 'Midwest']
            current_region = None
            
            for strong_tag in soup.find_all('strong'):
                text = strong_tag.text.strip()
                
                # Check if the text contains one of our region names followed by "First Four"
                for region_name in regions_to_find:
                    if f"{region_name} First" in text:
                        current_region = region_name
                        # Find the parent div that contains the bracket
                        parent = strong_tag
                        max_levels = 5
                        level = 0
                        
                        # Move up the DOM until we find the parent div
                        while parent and level < max_levels:
                            parent = parent.parent
                            if parent and parent.name == 'div' and parent.find('div', {'id': 'bracket'}):
                                region_divs[region_name] = parent
                                if debug:
                                    print(f"Found {region_name} region div by searching up from 'First Four' text")
                                break
                            level += 1
        
        # If still no region divs found, try searching for div with id="bracket"
        if not region_divs:
            all_brackets = soup.find_all('div', {'id': 'bracket'})
            for i, bracket in enumerate(all_brackets):
                if i < len(['East', 'West', 'South', 'Midwest']):
                    region_name = ['East', 'West', 'South', 'Midwest'][i]
                    region_divs[region_name] = bracket
                    if debug:
                        print(f"Assigning {region_name} to bracket div #{i+1}")
        
        # Process each region div we found
        for region_name, region_div in region_divs.items():
            if debug:
                print(f"Processing {region_name} region")
            
            # Find all team links in this region
            team_links = region_div.find_all('a', href=lambda href: href and "/cbb/schools/" in href)
            
            for link in team_links:
                # Get the parent div to check for seed number
                parent_div = link.parent
                
                # Try to find the seed - first check for a span directly before the link
                seed_span = parent_div.find('span')
                if seed_span and seed_span.text.strip().isdigit():
                    seed = int(seed_span.text.strip())
                    team_name = link.text.strip()
                    
                    # Avoid duplicate entries (e.g. same team listed multiple times in the bracket)
                    if not any(t['Team'] == team_name and t['Seed'] == seed and t['Region'] == region_name for t in tournament_teams):
                        tournament_teams.append({
                            'Team': team_name,
                            'Seed': seed,
                            'Region': region_name
                        })
                        
                        if debug:
                            print(f"Found team: {team_name} (Seed: {seed}, Region: {region_name})")
            
            # If no teams found, try alternative approach looking for text patterns
            if not any(t['Region'] == region_name for t in tournament_teams) and debug:
                print(f"No teams found for {region_name} using standard method, trying alternative")
                
                # Get all text content
                region_text = region_div.get_text()
                
                # Look for patterns like "1 Duke", "16 Alabama State", etc.
                lines = [line.strip() for line in region_text.split('\n') if line.strip()]
                
                for line in lines:
                    # Try to match seed and team pattern
                    seed_team_match = re.search(r'(\d{1,2})\s+([A-Za-z][\w\s&\'\-\.]+)', line)
                    if seed_team_match:
                        seed = int(seed_team_match.group(1))
                        team_name = seed_team_match.group(2).strip()
                        
                        # Simple validation - seeds should be 1-16
                        if 1 <= seed <= 16:
                            # Avoid duplicates
                            if not any(t['Team'] == team_name and t['Seed'] == seed and t['Region'] == region_name for t in tournament_teams):
                                tournament_teams.append({
                                    'Team': team_name,
                                    'Seed': seed,
                                    'Region': region_name
                                })
                                
                                if debug:
                                    print(f"Found team with text extraction: {team_name} (Seed: {seed}, Region: {region_name})")
        
        # Create DataFrame
        if tournament_teams:
            df = pd.DataFrame(tournament_teams)
            
            print(f"Successfully scraped {len(df)} tournament teams")
            
            # Save the raw data for debugging
            if debug:
                ensure_dir_exists("debug")
                raw_csv = os.path.join("debug", f"raw_tournament_{year}.csv")
                df.to_csv(raw_csv, index=False)
                print(f"Saved raw tournament data to {raw_csv} for debugging")
            
            return df
        else:
            print("Error: No tournament teams found")
            return None
        
    except requests.RequestException as e:
        print(f"Error fetching tournament data: {e}")
        return None
    except Exception as e:
        print(f"Error processing tournament data: {e}")
        import traceback
        traceback.print_exc()
        return None

def add_tournament_info(df: pd.DataFrame, tournament_teams_file: Optional[str] = None, debug: bool = False) -> pd.DataFrame:
    """
    Add tournament information (seed, region) to the ELO ratings.
    
    Args:
        df: DataFrame with ELO ratings
        tournament_teams_file: Path to CSV file with tournament teams info
        debug: Whether to print debug info
        
    Returns:
        DataFrame with added tournament information
    """
    if not isinstance(df, pd.DataFrame) or len(df) == 0:
        print("Warning: Empty or invalid ELO data, cannot add tournament information")
        return df
        
    if tournament_teams_file and os.path.exists(tournament_teams_file):
        try:
            tournament_df = pd.read_csv(tournament_teams_file)
            print(f"Tournament teams data contains {len(tournament_df)} teams")
            
            # Print sample of both dataframes for debugging
            if debug:
                print("\nELO Data Sample:")
                print(df.head())
                print("\nTournament Data Sample:")
                print(tournament_df.head())
            
            # Make sure columns exist
            if 'Team' not in df.columns:
                print("Error: 'Team' column missing from ELO data")
                return df
            if 'Team' not in tournament_df.columns:
                print("Error: 'Team' column missing from tournament data")
                return df
                
            # Using left join to keep all teams from the ELO ratings
            try:
                merged_df = pd.merge(df, tournament_df, on='Team', how='left')
                
                # Handle duplicate columns (e.g., if there's Seed_x and Seed_y)
                if 'Seed_x' in merged_df.columns and 'Seed_y' in merged_df.columns:
                    merged_df['Seed'] = merged_df['Seed_y'].fillna(merged_df['Seed_x'])
                    merged_df = merged_df.drop(['Seed_x', 'Seed_y'], axis=1)
                
                if 'Region_x' in merged_df.columns and 'Region_y' in merged_df.columns:
                    merged_df['Region'] = merged_df['Region_y'].fillna(merged_df['Region_x'])
                    merged_df = merged_df.drop(['Region_x', 'Region_y'], axis=1)
                
                # Count teams that have tournament information
                teams_in_tourney = len(merged_df.dropna(subset=['Seed', 'Region']))
                
                print(f"Found {teams_in_tourney} teams in the tournament")
                return merged_df
            except Exception as e:
                print(f"Error during merge: {e}")
                if debug:
                    import traceback
                    traceback.print_exc()
            
        except Exception as e:
            print(f"Error processing tournament data: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            print("Returning original ELO data without tournament information")
    
    # If no tournament file or error occurred, return original DataFrame
    return df

def ensure_dir_exists(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Directory path to check/create
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def main() -> int:
    """
    Main function to scrape data and save to CSV.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(description='Scrape data for March Madness bracket predictor')
    parser.add_argument('--year', type=int, default=None,
                        help='Year to scrape data for (defaults to current year)')
    parser.add_argument('--url', default=None,
                        help='Override URL of the data page')
    parser.add_argument('--output', default=None,
                        help='Output file path')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    parser.add_argument('--type', choices=['elo', 'tournament', 'both'], default='elo',
                        help='Type of data to scrape: ELO ratings, tournament teams, or both')
    
    args = parser.parse_args()
    
    # Determine output files
    year = args.year
    if year is None:
        current_year = datetime.datetime.now().year
        if datetime.datetime.now().month < 6:
            year = current_year
        else:
            year = current_year + 1
    
    year_dir = str(year)
    ensure_dir_exists(year_dir)
    
    elo_output = args.output if args.output else os.path.join(year_dir, "elo_ratings.csv")
    tournament_output = os.path.join(year_dir, "tournament_teams.csv")
    
    success = True
    
    # Scrape ELO ratings if requested
    if args.type in ['elo', 'both']:
        elo_df = scrape_elo_ratings(year, args.url, args.debug)
        if elo_df is not None:
            elo_df.to_csv(elo_output, index=False)
            print(f"Saved ELO ratings to {elo_output}")
        else:
            print("Error: Failed to scrape ELO ratings")
            success = False
    
    # Scrape tournament teams if requested
    if args.type in ['tournament', 'both']:
        tournament_df = scrape_tournament_teams(year, args.url, args.debug)
        if tournament_df is not None:
            tournament_df.to_csv(tournament_output, index=False)
            print(f"Saved tournament teams to {tournament_output}")
        else:
            print("Error: Failed to scrape tournament teams")
            success = False
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 