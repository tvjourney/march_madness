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
import difflib

# Known team name aliases: maps alternative/display names -> canonical ELO name
# Add entries here whenever a tournament team name doesn't match the ELO source
TEAM_NAME_ALIASES: Dict[str, str] = {
    # UConn variants
    "uconn": "Connecticut",
    "connecticut (uconn)": "Connecticut",
    # UNC variants
    "unc": "North Carolina",
    "north carolina (unc)": "North Carolina",
    # St. John's variants
    "st. john's (ny)": "Saint John's",
    "st. john's": "Saint John's",
    "st johns": "Saint John's",
    # Saint Mary's variants
    "saint mary's": "Saint Mary's (CA)",
    "st. mary's": "Saint Mary's (CA)",
    "st. mary's (ca)": "Saint Mary's (CA)",
    # LIU variants
    "liu": "Long Island",
    "long island university": "Long Island",
    # Queens variants
    "queens (nc)": "Queens",
    "queens university of charlotte": "Queens",
    # Arkansas-Pine Bluff
    "arkansas-pine bluff": "Ark.-Pine Bluff",
    # Mississippi Valley State
    "mississippi valley st.": "Mississippi Valley St.",
    # Texas A&M variants
    "texas a&m-corpus christi": "Texas A&M-CC",
    # UC variants
    "uc santa barbara": "UCSB",
    "uc irvine": "UC Irvine",
    "uc davis": "UC Davis",
    "uc san diego": "UC San Diego",
    # Nevada Las Vegas
    "unlv": "Nevada-Las Vegas",
    # Fresno State
    "fresno st.": "Fresno State",
    "fresno st": "Fresno State",
    # Miami variants
    "miami (oh)": "Miami (OH)",
    "miami (ohio)": "Miami (OH)",
    # Others
    "vmi": "VMI",
    "southeastern louisiana": "SE Louisiana",
    "se louisiana": "SE Louisiana",
    "app state": "Appalachian State",
    "appalachian st.": "Appalachian State",
    "morehead st.": "Morehead State",
    "morehead st": "Morehead State",
    "siu edwardsville": "SIU-Edwardsville",
    "siue": "SIU-Edwardsville",
    "montana st.": "Montana State",
    "montana st": "Montana State",
    "south dakota st.": "South Dakota State",
    "south dakota st": "South Dakota State",
    "north dakota st.": "North Dakota State",
    "north dakota st": "North Dakota State",
    "cal poly": "Cal Poly",
    "cal poly slo": "Cal Poly",
    "texas southern": "Texas Southern",
    "grambling": "Grambling State",
    "grambling st.": "Grambling State",
    "jackson st.": "Jackson State",
    "jackson st": "Jackson State",
    "prairie view a&m": "Prairie View",
    "prairie view": "Prairie View",
    "fiu": "FIU",
    "florida international": "FIU",
    "njit": "NJIT",
    "umbc": "UMBC",
    "uab": "UAB",
    "utsa": "UTSA",
    "utep": "UTEP",
    "vcu": "VCU",
    "usc": "Southern California",
    "smu": "SMU",
    "tcu": "TCU",
    "ole miss": "Mississippi",
    "pitt": "Pittsburgh",
    "ohio st.": "Ohio State",
    "ohio st": "Ohio State",
    "mich state": "Michigan State",
    "mich st.": "Michigan State",
    "penn st.": "Penn State",
    "penn st": "Penn State",
    "n.c. state": "NC State",
    "nc st.": "NC State",
    "nc st": "NC State",
    "north carolina st.": "NC State",
    "north carolina state": "NC State",
    "lsu": "LSU",
    "southern miss": "Southern Mississippi",
    "southern miss.": "Southern Mississippi",
    "central florida": "UCF",
    "unc wilmington": "UNCW",
    "unc greensboro": "UNC Greensboro",
    "unc asheville": "UNC Asheville",
    "byu": "BYU",
    "brigham young": "BYU",
    "umass": "Massachusetts",
    "u mass": "Massachusetts",
    "uc-davis": "UC Davis",
    "st. bonaventure": "St. Bonaventure",
    "st. joseph's": "Saint Joseph's",
    "st. joseph's (pa)": "Saint Joseph's",
    "loyola (il)": "Loyola Chicago",
    "loyola-chicago": "Loyola Chicago",
    "loyola chicago": "Loyola Chicago",
    "texas a&m-cc": "Texas A&M-CC",
    "kent st.": "Kent State",
    "kent st": "Kent State",
    "miami fl": "Miami (FL)",
    "miami (fl)": "Miami (FL)",
    "miami florida": "Miami (FL)",
    "northern iowa": "N. Iowa",
    "n. iowa": "N. Iowa",
}


def normalize_team_name(name: str) -> str:
    """
    Normalize a team name for matching purposes.
    Lowercases, strips extra whitespace, and removes common qualifiers.
    """
    normalized = name.strip().lower()
    # Remove trailing state/qualifier in parentheses for primary match attempt
    normalized = re.sub(r'\s*\((?:ny|ca|oh|fl|pa|il|tx|va|nc|sc)\)\s*$', '', normalized)
    # Remove common institutional suffixes so e.g. "Saint Mary's College" matches "Saint Mary's"
    normalized = re.sub(r'\s+college\s*$', '', normalized)
    normalized = re.sub(r'\s+university\s*$', '', normalized)
    # Normalize punctuation
    normalized = normalized.replace('.', '').replace("'", "'").replace('–', '-')
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def find_best_team_match(name: str, candidates: List[str], threshold: float = 0.75) -> Optional[str]:
    """
    Find the best matching team name from a list of candidates.

    Tries in order:
    1. Exact match
    2. Alias lookup (TEAM_NAME_ALIASES)
    3. Case-insensitive exact match
    4. Normalized name match
    5. Fuzzy match using difflib (if score >= threshold)

    Args:
        name: The team name to look up
        candidates: List of candidate names to match against
        threshold: Minimum fuzzy match score (0-1) to accept

    Returns:
        The best matching candidate name, or None if no match found
    """
    # 1. Exact match
    if name in candidates:
        return name

    # 2. Alias lookup
    alias_key = name.strip().lower()
    if alias_key in TEAM_NAME_ALIASES:
        canonical = TEAM_NAME_ALIASES[alias_key]
        if canonical in candidates:
            return canonical

    # 3. Case-insensitive exact match
    name_lower = name.strip().lower()
    candidates_lower = {c.lower(): c for c in candidates}
    if name_lower in candidates_lower:
        return candidates_lower[name_lower]

    # 4. Normalized match (strip qualifiers)
    name_norm = normalize_team_name(name)
    for cand in candidates:
        if normalize_team_name(cand) == name_norm:
            return cand

    # 5. Fuzzy match
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=threshold)
    if matches:
        return matches[0]

    # Try fuzzy on lowercase
    matches_lower = difflib.get_close_matches(name_lower, list(candidates_lower.keys()), n=1, cutoff=threshold)
    if matches_lower:
        return candidates_lower[matches_lower[0]]

    return None

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
        
        # Fallback: if any seeds are missing, search for First Four teams elsewhere on the page.
        # Sports-reference lists First Four participants in a separate section; those slots in
        # the main bracket show as TBD (no link), so the region-div pass misses them.
        seeds_per_region: Dict[str, set] = {}
        for t in tournament_teams:
            seeds_per_region.setdefault(t['Region'], set()).add(t['Seed'])

        # Build the set of (seed, region) slots that are still genuinely missing.
        # Only fill these slots — never overwrite or duplicate correctly-found teams.
        missing_slots: set = set()
        for r in ['East', 'West', 'South', 'Midwest']:
            for s in range(1, 17):
                if s not in seeds_per_region.get(r, set()):
                    missing_slots.add((s, r))

        if missing_slots:
            if debug:
                print(f"Bracket incomplete — searching page for First Four teams to fill {len(missing_slots)} slot(s): {missing_slots}")

            found_keys = {(t['Team'], t['Seed'], t['Region']) for t in tournament_teams}

            # Region keywords ordered longest-first so 'midwest' is checked before 'west',
            # preventing 'west' from matching inside 'midwest'.
            region_patterns = [
                (re.compile(r'(?<![a-z])midwest(?![a-z])'), 'Midwest'),
                (re.compile(r'(?<![a-z])east(?![a-z])'),    'East'),
                (re.compile(r'(?<![a-z])west(?![a-z])'),    'West'),
                (re.compile(r'(?<![a-z])south(?![a-z])'),   'South'),
            ]

            all_links = soup.find_all('a', href=lambda h: h and '/cbb/schools/' in h)
            for link in all_links:
                team_name = link.text.strip()
                if not team_name:
                    continue

                # Seed: look only at DIRECT children of the link's immediate parent
                # (avoids picking up score numbers from deeper descendants).
                seed = None
                parent = link.parent
                for _ in range(3):
                    if parent is None:
                        break
                    for span in parent.find_all('span', recursive=False):
                        txt = span.text.strip()
                        if txt.isdigit() and 1 <= int(txt) <= 16:
                            seed = int(txt)
                            break
                    if seed is not None:
                        break
                    parent = parent.parent
                if seed is None:
                    continue

                # Region: walk up ancestors; use word-boundary regex (midwest before west).
                region = None
                node = link.parent
                for _ in range(15):
                    if node is None:
                        break
                    node_id = (node.get('id') or '').lower()
                    for pattern, region_name in region_patterns:
                        if pattern.search(node_id):
                            region = region_name
                            break
                    if region:
                        break
                    node = node.parent

                # Only add the team if it fills a slot that is genuinely missing.
                if region and (seed, region) in missing_slots:
                    key = (team_name, seed, region)
                    if key not in found_keys:
                        tournament_teams.append({'Team': team_name, 'Seed': seed, 'Region': region})
                        found_keys.add(key)
                        missing_slots.discard((seed, region))
                        if debug:
                            print(f"Page-wide search found: {team_name} (Seed: {seed}, Region: {region})")
                        if not missing_slots:
                            break  # all missing slots filled

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
                
            # Before merging, resolve name mismatches using alias + fuzzy matching.
            # Build a mapping from tournament team names to ELO team names.
            elo_names = list(df['Team'])
            name_mapping: Dict[str, str] = {}
            unresolved: List[str] = []

            for t_name in tournament_df['Team']:
                match = find_best_team_match(t_name, elo_names)
                if match:
                    if match != t_name:
                        if debug:
                            print(f"Name match: '{t_name}' -> '{match}'")
                    name_mapping[t_name] = match
                else:
                    unresolved.append(t_name)

            if unresolved:
                print(f"Note: {len(unresolved)} tournament team(s) could not be matched to ELO data: "
                      f"{unresolved}")

            # Apply the name mapping to tournament_df for the merge
            tournament_df_mapped = tournament_df.copy()
            tournament_df_mapped['Team'] = tournament_df_mapped['Team'].map(
                lambda n: name_mapping.get(n, n)
            )

            # Using left join to keep all teams from the ELO ratings
            try:
                merged_df = pd.merge(df, tournament_df_mapped, on='Team', how='left')

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

def scrape_tournament_teams_espn(year: Optional[int] = None, debug: bool = False) -> Optional[pd.DataFrame]:
    """
    Scrape NCAA tournament team information from ESPN as a fallback source.

    Args:
        year: The year to scrape tournament data for. Defaults to current year.
        debug: Whether to save debug files

    Returns:
        DataFrame containing tournament team information or None if scraping failed
    """
    if year is None:
        current_year = datetime.datetime.now().year
        year = current_year if datetime.datetime.now().month < 6 else current_year + 1

    url = "https://www.espn.com/mens-college-basketball/bracket"

    try:
        print(f"Fetching tournament bracket from ESPN: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        if debug:
            ensure_dir_exists("debug")
            debug_html = os.path.join("debug", f"espn_bracket_{year}.html")
            with open(debug_html, "w", encoding="utf-8") as f:
                f.write(response.text)

        soup = BeautifulSoup(response.text, 'html.parser')

        tournament_teams = []

        # ESPN embeds bracket data in JSON within a <script> tag
        # Look for __espnfitt__ or similar embedded JSON
        for script_tag in soup.find_all('script'):
            script_text = script_tag.string or ''
            if 'competitors' not in script_text and 'seeds' not in script_text.lower():
                continue

            # Try to find bracket JSON data
            json_match = re.search(r'window\[[\'"](.*?)[\'"]\]\s*=\s*(\{.*?\});', script_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r'__espnfitt__\s*=\s*(\{.*\})\s*;', script_text, re.DOTALL)
            if json_match:
                try:
                    import json
                    data_str = json_match.group(2) if json_match.lastindex >= 2 else json_match.group(1)
                    bracket_data = json.loads(data_str)
                    # Walk the JSON looking for team/seed/region entries
                    _extract_espn_teams(bracket_data, tournament_teams)
                    if tournament_teams:
                        break
                except Exception:
                    pass

        # Fallback: parse visible HTML for seed + team name patterns
        if not tournament_teams:
            # ESPN uses elements like <span class="seed">1</span><span class="name">Duke</span>
            for seed_el in soup.find_all(class_=re.compile(r'\bseed\b')):
                try:
                    seed_val = int(seed_el.get_text(strip=True))
                except ValueError:
                    continue

                # Try sibling/parent for team name
                parent = seed_el.parent
                name_el = parent.find(class_=re.compile(r'\bname\b|\bteam-name\b'))
                if not name_el:
                    # Try next sibling text
                    siblings = list(seed_el.next_siblings)
                    for sib in siblings[:3]:
                        text = getattr(sib, 'get_text', lambda **kw: str(sib))(strip=True)
                        if text and not text.isdigit():
                            name_el = sib
                            break

                if name_el:
                    team_name = getattr(name_el, 'get_text', lambda **kw: str(name_el))(strip=True)
                    if team_name and 1 <= seed_val <= 16:
                        tournament_teams.append({'Team': team_name, 'Seed': seed_val, 'Region': None})

        if not tournament_teams:
            if debug:
                print("ESPN scraper: no teams found in HTML or JSON")
            return None

        df = pd.DataFrame(tournament_teams).drop_duplicates(subset=['Team', 'Seed'])
        print(f"ESPN fallback: found {len(df)} teams")
        return df

    except requests.RequestException as e:
        print(f"ESPN fallback scraper failed: {e}")
        return None
    except Exception as e:
        if debug:
            print(f"ESPN fallback scraper error: {e}")
            import traceback
            traceback.print_exc()
        return None


def _extract_espn_teams(data: Any, results: List[Dict[str, Any]]) -> None:
    """Recursively walk ESPN JSON to extract team name / seed / region info."""
    if isinstance(data, dict):
        # Look for patterns like {"seed": 1, "team": {"shortDisplayName": "Duke"}, "groupId": ...}
        seed = data.get('seed') or data.get('seedNumber')
        team_block = data.get('team') or data.get('competitor')
        region = data.get('groupName') or data.get('region')

        if seed and team_block and isinstance(team_block, dict):
            team_name = (team_block.get('displayName')
                         or team_block.get('shortDisplayName')
                         or team_block.get('name', ''))
            if team_name:
                try:
                    seed_int = int(seed)
                    if 1 <= seed_int <= 16:
                        results.append({
                            'Team': team_name,
                            'Seed': seed_int,
                            'Region': str(region).capitalize() if region else None,
                        })
                except (ValueError, TypeError):
                    pass

        for v in data.values():
            _extract_espn_teams(v, results)
    elif isinstance(data, list):
        for item in data:
            _extract_espn_teams(item, results)


def fill_missing_seeds(
    tournament_df: pd.DataFrame,
    year: Optional[int] = None,
    debug: bool = False,
) -> pd.DataFrame:
    """
    Attempt to fill in any missing seeds/regions in tournament_df using ESPN as a fallback.

    A complete tournament has seeds 1-16 in each of 4 regions (64 teams).
    If seeds are missing, scrapes ESPN and merges in the missing entries.

    Args:
        tournament_df: Existing tournament teams DataFrame (Team, Seed, Region)
        year: Tournament year
        debug: Whether to print debug info

    Returns:
        Updated DataFrame with missing seeds filled where possible
    """
    regions = ['East', 'West', 'South', 'Midwest']
    missing: List[Tuple[str, int]] = []  # (region, seed)

    for region in regions:
        region_df = tournament_df[tournament_df['Region'] == region]
        present_seeds = set(region_df['Seed'].dropna().astype(int))
        for s in range(1, 17):
            if s not in present_seeds:
                missing.append((region, s))

    if not missing:
        return tournament_df

    print(f"Attempting to fill {len(missing)} missing seed(s) from ESPN...")

    espn_df = scrape_tournament_teams_espn(year, debug=debug)
    if espn_df is None or espn_df.empty:
        print("Warning: ESPN fallback returned no data. Missing seeds remain as TBD.")
        return tournament_df

    rows_added = []
    for region, seed in missing:
        # Try to find this seed in the ESPN data
        # If ESPN has region info, use it; otherwise match by seed
        candidates = espn_df[espn_df['Seed'] == seed]
        if candidates.empty:
            print(f"Warning: Could not find seed {seed} in ESPN data for {region} region.")
            continue

        if 'Region' in candidates.columns and candidates['Region'].notna().any():
            region_match = candidates[candidates['Region'].str.lower() == region.lower()]
            if not region_match.empty:
                row = region_match.iloc[0]
            else:
                # No region match - if only one entry for this seed, use it cautiously
                if len(candidates) == 1:
                    row = candidates.iloc[0]
                else:
                    print(f"Warning: Ambiguous ESPN data for seed {seed} (no {region} region match).")
                    continue
        else:
            if len(candidates) == 1:
                row = candidates.iloc[0]
            else:
                print(f"Warning: Ambiguous ESPN data for seed {seed} - multiple teams, no region info.")
                continue

        team_name = row['Team']
        print(f"Filling missing seed {seed} in {region} with '{team_name}' (from ESPN)")
        rows_added.append({'Team': team_name, 'Seed': seed, 'Region': region})

    if rows_added:
        added_df = pd.DataFrame(rows_added)
        tournament_df = pd.concat([tournament_df, added_df], ignore_index=True)

    return tournament_df


def scrape_advanced_stats(year: Optional[int] = None, debug: bool = False) -> Optional[pd.DataFrame]:
    """
    Scrape advanced team stats (adjusted offensive/defensive efficiency, tempo) from barttorvik.com.
    These are KenPom-equivalent metrics available publicly via T-Rank.

    Args:
        year: The season year to scrape. Defaults to current year.
        debug: Whether to save debug files.

    Returns:
        DataFrame with columns: Team, AdjOE, AdjDE, AdjT, NetRtg, TRank
        or None if scraping failed.
    """
    if year is None:
        current_year = datetime.datetime.now().year
        year = current_year if datetime.datetime.now().month < 6 else current_year + 1

    url = f"https://www.barttorvik.com/trank.php?year={year}&sort=&top=0&conlimit=All"

    try:
        print(f"Fetching advanced stats from {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        if debug:
            ensure_dir_exists("debug")
            debug_html = os.path.join("debug", f"advanced_stats_{year}.html")
            with open(debug_html, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"Saved HTML to {debug_html} for debugging")

        soup = BeautifulSoup(response.text, 'html.parser')

        # barttorvik uses a table with id="t-rank-table" or similar
        table = soup.find('table', {'id': 't-rank-table'})
        if not table:
            table = soup.find('table')

        if not table:
            print("Error: Could not find stats table on barttorvik.com")
            return None

        rows = table.find_all('tr')
        if not rows:
            print("Error: No rows found in stats table")
            return None

        # Parse header to find column indices
        header_row = rows[0]
        headers_cells = [th.text.strip() for th in header_row.find_all(['th', 'td'])]
        if debug:
            print(f"Table headers: {headers_cells}")

        # Column name mapping (barttorvik uses shorthand names)
        col_map = {
            'team': None, 'adjoe': None, 'adjde': None, 'adjt': None, 'rk': None
        }
        for i, h in enumerate(headers_cells):
            h_lower = h.lower().replace(' ', '').replace('.', '')
            if h_lower in ('team', 'teamname'):
                col_map['team'] = i
            elif h_lower in ('adjoe', 'adjo', 'offeff', 'adjoffeff'):
                col_map['adjoe'] = i
            elif h_lower in ('adjde', 'adjd', 'defeff', 'adjdefeff'):
                col_map['adjde'] = i
            elif h_lower in ('adjt', 'adjtempo', 'tempo'):
                col_map['adjt'] = i
            elif h_lower in ('rk', 'rank', 'trank'):
                col_map['rk'] = i

        data = []
        for row in rows[1:]:
            cells = row.find_all('td')
            if not cells:
                continue

            def get_cell_text(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx].text.strip()

            # Try to get team name from link first
            team_name = None
            team_idx = col_map['team']
            if team_idx is not None and team_idx < len(cells):
                link = cells[team_idx].find('a')
                team_name = link.text.strip() if link else cells[team_idx].text.strip()

            if not team_name:
                continue

            try:
                adj_oe = float(get_cell_text(col_map['adjoe'])) if col_map['adjoe'] is not None else None
                adj_de = float(get_cell_text(col_map['adjde'])) if col_map['adjde'] is not None else None
                adj_t = float(get_cell_text(col_map['adjt'])) if col_map['adjt'] is not None else None
                t_rank_str = get_cell_text(col_map['rk'])
                t_rank = int(t_rank_str) if t_rank_str.isdigit() else None
            except (ValueError, TypeError):
                continue

            net_rtg = round(adj_oe - adj_de, 2) if adj_oe is not None and adj_de is not None else None

            data.append({
                'Team': team_name,
                'AdjOE': adj_oe,
                'AdjDE': adj_de,
                'AdjT': adj_t,
                'NetRtg': net_rtg,
                'TRank': t_rank
            })

        if not data:
            print("Error: No advanced stats rows parsed")
            return None

        df = pd.DataFrame(data)
        print(f"Successfully scraped advanced stats for {len(df)} teams")

        if debug:
            raw_csv = os.path.join("debug", f"raw_advanced_stats_{year}.csv")
            df.to_csv(raw_csv, index=False)
            print(f"Saved raw data to {raw_csv}")

        return df

    except requests.RequestException as e:
        print(f"Error fetching advanced stats: {e}")
        return None
    except Exception as e:
        print(f"Error processing advanced stats: {e}")
        import traceback
        traceback.print_exc()
        return None


def scrape_historical_results(
    start_year: int = 2010,
    end_year: Optional[int] = None,
    debug: bool = False
) -> Optional[pd.DataFrame]:
    """
    Scrape historical NCAA tournament game results from sports-reference.com.

    Pulls results year-by-year and computes upset rates by seed matchup and round,
    storing them as a flat DataFrame of individual game outcomes.

    Args:
        start_year: First year to include (default 2010).
        end_year: Last year to include (default: current year - 1).
        debug: Whether to save debug files.

    Returns:
        DataFrame with columns: Year, Round, HigherSeed, LowerSeed, Winner, Upset
        or None if all scraping failed.
    """
    if end_year is None:
        end_year = datetime.datetime.now().year - 1

    round_name_map = {
        'First Round': 1, 'Second Round': 2,
        'Sweet Sixteen': 3, 'Elite Eight': 4,
        'Final Four': 5, 'National Championship': 6,
        # alternate spellings
        'Sweet 16': 3, 'Elite 8': 4,
    }

    all_games: List[Dict[str, Any]] = []

    for year in range(start_year, end_year + 1):
        url = f"https://www.sports-reference.com/cbb/postseason/men/{year}-ncaa.html"
        try:
            print(f"Fetching {year} tournament results from sports-reference.com...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            if debug:
                ensure_dir_exists("debug")
                debug_html = os.path.join("debug", f"tournament_results_{year}.html")
                with open(debug_html, "w", encoding="utf-8") as f:
                    f.write(response.text)

            soup = BeautifulSoup(response.text, 'html.parser')

            # Each game is represented as a div with class "game" or similar
            # sports-reference bracket pages list scores in a bracket structure
            # We look for score divs grouped by round
            current_round_num = None

            for tag in soup.find_all(['h2', 'h3', 'div']):
                # Detect round headers
                if tag.name in ('h2', 'h3'):
                    text = tag.text.strip()
                    for round_name, round_num in round_name_map.items():
                        if round_name.lower() in text.lower():
                            current_round_num = round_num
                            break

                # Parse game score blocks: look for divs containing seed + team score pairs
                if tag.name == 'div' and 'game' in tag.get('class', []):
                    teams_in_game = tag.find_all('div', class_=re.compile(r'team'))
                    if len(teams_in_game) < 2:
                        continue

                    game_teams = []
                    for team_div in teams_in_game[:2]:
                        seed_span = team_div.find('span', class_=re.compile(r'seed'))
                        seed_val = None
                        if seed_span:
                            try:
                                seed_val = int(seed_span.text.strip())
                            except ValueError:
                                pass

                        name_span = team_div.find('span', class_=re.compile(r'name|short'))
                        team_name = name_span.text.strip() if name_span else ""

                        score_span = team_div.find('span', class_=re.compile(r'score|pts'))
                        score_val = None
                        if score_span:
                            try:
                                score_val = int(score_span.text.strip())
                            except ValueError:
                                pass

                        game_teams.append({'name': team_name, 'seed': seed_val, 'score': score_val})

                    if len(game_teams) == 2 and all(t['seed'] is not None for t in game_teams):
                        t1, t2 = game_teams
                        higher = t1 if t1['seed'] < t2['seed'] else t2
                        lower = t2 if t1['seed'] < t2['seed'] else t1

                        if t1['score'] is not None and t2['score'] is not None:
                            winner_seed = t1['seed'] if t1['score'] > t2['score'] else t2['seed']
                            upset = winner_seed == lower['seed']

                            all_games.append({
                                'Year': year,
                                'Round': current_round_num,
                                'HigherSeed': higher['seed'],
                                'LowerSeed': lower['seed'],
                                'HigherSeedTeam': higher['name'],
                                'LowerSeedTeam': lower['name'],
                                'Winner': 'lower' if upset else 'higher',
                                'Upset': upset
                            })

        except requests.RequestException as e:
            print(f"Warning: Could not fetch {year} tournament data: {e}")
        except Exception as e:
            print(f"Warning: Error processing {year} tournament data: {e}")
            if debug:
                import traceback
                traceback.print_exc()

    if not all_games:
        print("Warning: No historical game data could be scraped. "
              "sports-reference.com bracket pages may use JavaScript rendering.")
        return None

    df = pd.DataFrame(all_games)
    print(f"Scraped {len(df)} historical tournament games ({start_year}–{end_year})")

    if debug:
        ensure_dir_exists("debug")
        df.to_csv(os.path.join("debug", "historical_results.csv"), index=False)

    return df


def compute_historical_upset_rates(historical_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute upset rates by seed matchup and round from historical game data.

    Args:
        historical_df: DataFrame from scrape_historical_results().

    Returns:
        DataFrame with columns: HigherSeed, LowerSeed, Round, Games, Upsets, UpsetRate
    """
    if historical_df is None or historical_df.empty:
        return pd.DataFrame()

    groups = historical_df.groupby(['HigherSeed', 'LowerSeed', 'Round'])
    records = []
    for (higher, lower, rnd), group in groups:
        games = len(group)
        upsets = group['Upset'].sum()
        records.append({
            'HigherSeed': higher,
            'LowerSeed': lower,
            'Round': rnd,
            'Games': games,
            'Upsets': int(upsets),
            'UpsetRate': round(upsets / games, 4) if games > 0 else 0.0
        })

    return pd.DataFrame(records).sort_values(['Round', 'HigherSeed'])


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