#!/usr/bin/env python3
"""
March Madness Bracket Predictor

This script predicts a March Madness tournament bracket based on ELO ratings with 10% randomness.
It obtains ELO ratings from data sources, processes the tournament bracket, and simulates matchups.
"""

import pandas as pd
import random
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import json
import os

@dataclass
class Team:
    """Represents a basketball team in the tournament."""
    name: str
    seed: int
    elo: float
    region: str
    is_tbd: bool = False
    
    def __str__(self) -> str:
        return f"{self.seed}. {self.name} (ELO: {self.elo:.0f})"

@dataclass
class Matchup:
    """Represents a matchup between two teams."""
    team1: Team
    team2: Team
    round_num: int
    region: str
    game_id: int
    unique_game_id: int = 0  # Unique ID across all rounds
    
    def simulate(self, randomness_factor: float = 0.1) -> Team:
        """
        Simulate the matchup between two teams with seed-based randomness.
        
        Args:
            randomness_factor: Base randomness factor, used for non-seed-specific adjustments
        
        Returns:
            The winning Team object
        """
        # TBD teams always lose in the first round
        if self.team1.is_tbd and self.round_num == 1:
            return self.team2
        
        if self.team2.is_tbd and self.round_num == 1:
            return self.team1
        
        # Use seed-based randomness for more realistic tournament outcomes
        return self.simulate_with_seed_based_randomness()
    
    def simulate_with_seed_based_randomness(self) -> Team:
        """
        Simulate matchup using randomness calibrated to historical upset rates by seed.
        
        Instead of applying a flat randomness factor, this method adjusts each team's ELO
        based on the historical upset patterns observed in March Madness.
        
        Returns:
            The winning Team object
        """
        # Don't modify original ELO values
        team1_adjusted_elo = self.team1.elo
        team2_adjusted_elo = self.team2.elo
        
        # Get seed matchup (use lower number as higher seed)
        higher_seed = min(self.team1.seed, self.team2.seed)
        lower_seed = max(self.team1.seed, self.team2.seed)
        
        # For first round games, apply seed-specific randomness based on historical data
        if self.round_num == 1:
            # Historical upset rates inform our randomness adjustment
            if higher_seed == 1 and lower_seed == 16:
                # 1v16: very small chance of upset (~1.3%)
                random_factor = 0.03
            elif higher_seed == 2 and lower_seed == 15:
                # 2v15: ~7.1% upset rate
                random_factor = 0.10
            elif higher_seed == 3 and lower_seed == 14:
                # 3v14: ~14.7% upset rate
                random_factor = 0.15
            elif higher_seed == 4 and lower_seed == 13:
                # 4v13: ~20.5% upset rate
                random_factor = 0.18
            elif higher_seed == 5 and lower_seed == 12:
                # 5v12: ~35.3% upset rate - the famous 12-5 upset
                random_factor = 0.27
            elif higher_seed == 6 and lower_seed == 11:
                # 6v11: ~39.1% upset rate
                random_factor = 0.30
            elif higher_seed == 7 and lower_seed == 10:
                # 7v10: ~38.7% upset rate
                random_factor = 0.30
            elif higher_seed == 8 and lower_seed == 9:
                # 8v9: Practically even (~51.9% for 9 seeds)
                random_factor = 0.40
            else:
                # For non-standard matchups, use a moderate randomness
                random_factor = 0.20
                
            # Apply randomness to both teams' ELO ratings
            team1_adjusted_elo *= random.uniform(1 - random_factor, 1 + random_factor)
            team2_adjusted_elo *= random.uniform(1 - random_factor, 1 + random_factor)
        else:
            # Later rounds: seed-dependent randomness that DECREASES for high seeds
            # This reflects that top seeds become more dominant in later rounds
            
            # Base randomness for later rounds
            round_random_factor = 0.20
            
            # Apply seed-specific adjustments for later rounds
            team1_seed = self.team1.seed
            team2_seed = self.team2.seed
            
            # Calculate seed-specific randomness factors
            # Higher seeds (1-3) get progressively less randomness in later rounds
            # Lower seeds maintain higher randomness
            def get_seed_factor(seed: int, round_num: int) -> float:
                """Calculate randomness factor based on seed and round."""
                if seed == 1:
                    # #1 seeds become more dominant in later rounds (Sweet 16: 79% win rate)
                    # Reduce randomness for each progressive round
                    return max(0.05, round_random_factor - (round_num - 1) * 0.04)
                elif seed == 2:
                    # #2 seeds also strong but not as dominant as #1
                    return max(0.08, round_random_factor - (round_num - 1) * 0.03)
                elif seed <= 4:
                    # #3-#4 seeds still relatively strong
                    return max(0.12, round_random_factor - (round_num - 1) * 0.02)
                elif seed <= 8:
                    # #5-#8 seeds - moderate randomness reduction
                    return max(0.15, round_random_factor - (round_num - 1) * 0.01)
                else:
                    # #9-#16 seeds - maintain high randomness or slightly increase
                    # Double-digit seeds that make it to later rounds often continue to surprise
                    return min(0.40, round_random_factor + (round_num - 1) * 0.05)
            
            # Get randomness factors for each team
            team1_factor = get_seed_factor(team1_seed, self.round_num)
            team2_factor = get_seed_factor(team2_seed, self.round_num)
            
            # Apply the randomness factors
            team1_adjusted_elo *= random.uniform(1 - team1_factor, 1 + team1_factor)
            team2_adjusted_elo *= random.uniform(1 - team2_factor, 1 + team2_factor)
            
            # Special case: Championship game advantage for #1 seeds (64.1% championship win rate)
            if self.round_num == 6:
                if team1_seed == 1:
                    team1_adjusted_elo *= 1.05  # Small boost for #1 seeds in championship
                if team2_seed == 1:
                    team2_adjusted_elo *= 1.05  # Small boost for #1 seeds in championship
        
        # Determine winner based on adjusted ELO
        if team1_adjusted_elo > team2_adjusted_elo:
            return self.team1
        else:
            return self.team2
    
    def __str__(self) -> str:
        return f"{self.team1} vs {self.team2} (Round {self.round_num}, {self.region}, Game {self.game_id}, UID: {self.unique_game_id})"

class BracketPredictor:
    """Class to predict March Madness bracket outcomes."""
    
    def __init__(self, randomness_factor: float = 0.1):
        """
        Initialize the bracket predictor.
        
        Args:
            randomness_factor: Amount of randomness to include in predictions (0-1)
        """
        self.teams: Dict[str, Team] = {}
        self.bracket: List[Matchup] = []
        self.results: Dict[int, List[Matchup]] = {}
        self.randomness_factor = randomness_factor
        self.round_names = {
            1: "First Round",
            2: "Second Round",
            3: "Sweet 16",
            4: "Elite Eight",
            5: "Final Four",
            6: "Championship"
        }
        # Expected number of matchups per round in a standard NCAA tournament
        self.expected_matchups_per_round = {
            1: 32,  # First round: 64 teams / 2
            2: 16,  # Second round: 32 teams / 2
            3: 8,   # Sweet 16: 16 teams / 2
            4: 4,   # Elite 8: 8 teams / 2
            5: 2,   # Final Four: 4 teams / 2
            6: 1    # Championship: 2 teams / 2
        }
        # Placeholder ELO for TBD teams - always lower than real teams
        self.tbd_elo = 1000.0
    
    def load_elo_ratings(self, filepath: Optional[str] = None) -> None:
        """
        Load ELO ratings from a CSV file.
        
        Args:
            filepath: Path to CSV file with ELO ratings
        """
        if filepath and os.path.exists(filepath):
            print(f"Loading ELO ratings from {filepath}")
            elo_data = pd.read_csv(filepath)
            
            # Check if the data includes seed and region information
            has_seed = 'Seed' in elo_data.columns
            has_region = 'Region' in elo_data.columns
            
            teams_data = []
            for _, row in elo_data.iterrows():
                team_info = {
                    "name": row['Team'],
                    "elo": float(row['ELO']),
                }
                
                # Add seed and region if available
                if has_seed:
                    team_info["seed"] = int(row['Seed'])
                if has_region:
                    team_info["region"] = row['Region']
                
                teams_data.append(team_info)
            
            # If the data is complete, set up the first round immediately
            if has_seed and has_region:
                self.setup_first_round(teams_data)
                return teams_data
            else:
                print("Warning: CSV file doesn't contain all necessary information (seed, region).")
                return teams_data
        else:
            print("No file provided or file doesn't exist. Please provide ELO data.")
            return None
    
    def load_tournament_bracket(self, filepath: Optional[str] = None) -> None:
        """
        Load the tournament bracket structure from a file.
        
        Args:
            filepath: Path to JSON/CSV file with bracket information
        """
        if filepath and os.path.exists(filepath):
            print(f"Loading tournament bracket from {filepath}")
            # Implementation depends on the format of the bracket data
        else:
            print("No bracket file provided or file doesn't exist.")
            # Could implement a manual entry or default bracket structure
    
    def create_tbd_team(self, seed: int, region: str) -> Team:
        """
        Create a TBD team for a given seed and region.
        
        Args:
            seed: The seed number for the TBD team
            region: The region for the TBD team
            
        Returns:
            A Team object representing a TBD team
        """
        return Team(
            name="TBD",
            seed=seed,
            elo=self.tbd_elo,
            region=region,
            is_tbd=True
        )
    
    def setup_first_round(self, teams_data: List[Dict[str, Any]]) -> None:
        """
        Set up the first round matchups based on seeds.
        
        Args:
            teams_data: List of dictionaries containing team information
        """
        # Create Team objects
        self.teams = {}
        for team_info in teams_data:
            team = Team(
                name=team_info["name"],
                seed=team_info["seed"],
                elo=team_info["elo"],
                region=team_info["region"]
            )
            self.teams[team.name] = team
        
        # Standard first-round matchups by seed
        seed_matchups = [(1, 16), (8, 9), (5, 12), (4, 13), (6, 11), (3, 14), (7, 10), (2, 15)]
        
        # Expected regions in a standard NCAA tournament
        expected_regions = ["East", "West", "South", "Midwest"]
        present_regions = set(team.region for team in self.teams.values())
        
        # Ensure all regions exist, add if missing
        for region in expected_regions:
            if region not in present_regions:
                print(f"Adding missing region: {region}")
                # We would add placeholder teams here, but this is unlikely
        
        # Group teams by region
        teams_by_region: Dict[str, Dict[int, Team]] = {}
        for team in self.teams.values():
            if team.region not in teams_by_region:
                teams_by_region[team.region] = {}
            teams_by_region[team.region][team.seed] = team
        
        # Create first-round matchups
        self.bracket = []
        game_id = 1
        regions = sorted(teams_by_region.keys())
        for region in regions:
            region_teams = teams_by_region[region]
            for seed1, seed2 in seed_matchups:
                team1 = region_teams.get(seed1)
                team2 = region_teams.get(seed2)
                
                # If either team is missing, create a TBD team
                if not team1:
                    team1 = self.create_tbd_team(seed1, region)
                    region_teams[seed1] = team1
                    print(f"Created TBD team for seed {seed1} in {region} region")
                
                if not team2:
                    team2 = self.create_tbd_team(seed2, region)
                    region_teams[seed2] = team2
                    print(f"Created TBD team for seed {seed2} in {region} region")
                
                matchup = Matchup(
                    team1=team1, 
                    team2=team2, 
                    round_num=1, 
                    region=region, 
                    game_id=game_id,
                    unique_game_id=game_id
                )
                self.bracket.append(matchup)
                game_id += 1
        
        expected = self.expected_matchups_per_round[1]
        if len(self.bracket) < expected:
            print(f"Warning: Only created {len(self.bracket)} first-round matchups. "
                  f"Expected {expected} matchups for a complete tournament.")
    
    def simulate_tournament(self) -> Dict[int, List[Tuple[Team, Team, Team, str, int, int]]]:
        """
        Simulate the entire tournament bracket.
        
        Returns:
            Dictionary mapping round numbers to lists of matchup results
        """
        results: Dict[int, List[Tuple[Team, Team, Team, str, int, int]]] = {}
        winners_by_region: Dict[str, List[Tuple[Team, int, int]]] = {}  # Now includes unique_game_id
        
        # Initialize with first round matchups
        current_round = 1
        current_matchups = self.bracket
        
        # Verify we have enough matchups for first round
        expected = self.expected_matchups_per_round[1]
        if len(current_matchups) < expected:
            print(f"Warning: Incomplete tournament. Only {len(current_matchups)} first-round matchups "
                  f"instead of expected {expected}.")
        
        # Initialize unique game ID counter - use the highest existing ID + 1
        next_unique_id = max([m.unique_game_id for m in current_matchups], default=0) + 1
        
        # Maximum of 6 rounds in March Madness (First Round to Championship)
        while current_round <= 6 and (current_matchups or current_round == 6):
            results[current_round] = []
            next_round_matchups = []
            
            # Reset winners by region for this round
            for region in set(m.region for m in current_matchups):
                winners_by_region[region] = []
            
            # Simulate current round matchups
            for matchup in current_matchups:
                winner = matchup.simulate(self.randomness_factor)
                results[current_round].append((
                    matchup.team1, 
                    matchup.team2, 
                    winner, 
                    matchup.region, 
                    matchup.game_id,
                    matchup.unique_game_id
                ))
                
                # Add winner to the appropriate region's winners list
                # Store the winner, original matchup game_id, and unique_game_id
                winners_by_region[matchup.region].append((winner, matchup.game_id, matchup.unique_game_id))
            
            # Create next round matchups
            if current_round < 4:  # Rounds within regions (before Elite Eight)
                game_id = 1
                regions = sorted(winners_by_region.keys())
                for region in regions:
                    winners = winners_by_region[region]
                    # Sort winners by game_id to maintain proper bracket order
                    sorted_winners = sorted(winners, key=lambda x: x[1])
                    winners_only = [w[0] for w in sorted_winners]
                    
                    # Pair adjacent winners for next round
                    for i in range(0, len(winners_only), 2):
                        if i + 1 < len(winners_only):
                            next_round_matchups.append(Matchup(
                                winners_only[i], winners_only[i+1], 
                                round_num=current_round+1,
                                region=region,
                                game_id=game_id,
                                unique_game_id=next_unique_id
                            ))
                            next_unique_id += 1
                            game_id += 1
            
            elif current_round == 4:  # Elite Eight to Final Four
                # Get regional champions (one winner from each region)
                regional_champions = []
                regions = sorted(winners_by_region.keys())
                for region in regions:
                    if winners_by_region[region]:
                        # Take the first winner from each region
                        regional_champions.append((winners_by_region[region][0][0], region))
                
                # Standard regions in order they typically appear in brackets
                standard_regions = ["East", "West", "South", "Midwest"]
                existing_regions = {r for _, r in regional_champions}
                
                # Fill in missing regions with TBD teams if needed
                for region in standard_regions:
                    if region not in existing_regions:
                        tbd_champion = self.create_tbd_team(seed=1, region=region)
                        regional_champions.append((tbd_champion, region))
                        print(f"Created TBD champion for missing {region} region")
                
                # Sort champions by region to ensure consistent matchups
                regional_champions.sort(key=lambda x: standard_regions.index(x[1]) if x[1] in standard_regions else 999)
                
                # Setup Final Four matchups (typically East vs West, South vs Midwest)
                if len(regional_champions) >= 4:
                    # First semifinal: East vs West
                    next_round_matchups.append(Matchup(
                        regional_champions[0][0],  # East champion
                        regional_champions[1][0],  # West champion
                        round_num=5,               # Final Four round
                        region="Final Four",       # Final Four region
                        game_id=1,
                        unique_game_id=next_unique_id
                    ))
                    next_unique_id += 1
                    
                    # Second semifinal: South vs Midwest
                    next_round_matchups.append(Matchup(
                        regional_champions[2][0],  # South champion
                        regional_champions[3][0],  # Midwest champion
                        round_num=5,               # Final Four round
                        region="Final Four",       # Final Four region
                        game_id=2,
                        unique_game_id=next_unique_id
                    ))
                    next_unique_id += 1
            
            elif current_round == 5:  # Final Four to Championship
                # Get the Final Four winners 
                final_four_winners = []
                
                # Simulate each Final Four matchup
                for matchup in current_matchups:
                    winner = matchup.simulate(self.randomness_factor)
                    final_four_winners.append(winner)
                
                # Store results in the Final Four round
                results[current_round] = [(matchup.team1, matchup.team2, winner, matchup.region, matchup.game_id, matchup.unique_game_id) 
                                         for matchup, winner in zip(current_matchups, final_four_winners)]
                
                # Create Championship matchup if we have two Final Four winners
                if len(final_four_winners) >= 2:
                    championship_matchup = Matchup(
                        final_four_winners[0],
                        final_four_winners[1],
                        round_num=6,               # Championship round
                        region="Championship",     # Championship region
                        game_id=1,
                        unique_game_id=next_unique_id
                    )
                    next_unique_id += 1
                    
                    # Simulate Championship game
                    champion = championship_matchup.simulate(self.randomness_factor)
                    results[6] = [(championship_matchup.team1, championship_matchup.team2, champion, "Championship", 1, championship_matchup.unique_game_id)]
                
                # No more rounds after Championship
                break
            
            # Move to next round
            current_round += 1
            current_matchups = next_round_matchups
            
            # Verify we have enough matchups for next round
            if current_round in self.expected_matchups_per_round:
                expected = self.expected_matchups_per_round[current_round]
                if len(next_round_matchups) < expected and next_round_matchups:
                    print(f"Warning: Round {current_round} ({self.round_names.get(current_round)}) has "
                          f"{len(next_round_matchups)} matchups instead of expected {expected}.")
        
        return results
    
    def print_bracket(self, results: Dict[int, List[Tuple[Team, Team, Team, str, int, int]]]) -> None:
        """
        Print the predicted bracket in a readable format.
        
        Args:
            results: Dictionary mapping round numbers to matchup results
        """
        for round_num in sorted(results.keys()):
            print(f"\n{self.round_names.get(round_num, f'Round {round_num}')}")
            print("=" * 50)
            
            for team1, team2, winner, region, game_id, unique_id in results[round_num]:
                team1_display = "TBD" if team1.is_tbd else f"{team1.seed}. {team1.name}"
                team2_display = "TBD" if team2.is_tbd else f"{team2.seed}. {team2.name}"
                winner_display = "TBD" if winner.is_tbd else f"{winner.seed}. {winner.name}"
                
                print(f"Game {game_id} (ID: {unique_id}): {team1_display} vs {team2_display} ({region})")
                print(f"Winner: {winner_display}")
                print("-" * 40)
    
    def export_bracket(self, results: Dict[int, List[Tuple[Team, Team, Team, str, int, int]]], filepath: str) -> None:
        """
        Export the bracket results to a JSON file.
        
        Args:
            results: Dictionary mapping round numbers to matchup results
            filepath: Path to save the JSON file
        """
        export_data = {}
        
        for round_num, matchups in results.items():
            round_name = self.round_names.get(round_num, f"Round {round_num}")
            export_data[round_name] = []
            
            for team1, team2, winner, region, game_id, unique_id in matchups:
                team1_display = "TBD" if team1.is_tbd else f"{team1.seed}. {team1.name}"
                team2_display = "TBD" if team2.is_tbd else f"{team2.seed}. {team2.name}"
                winner_display = "TBD" if winner.is_tbd else f"{winner.seed}. {winner.name}"
                
                matchup_data = {
                    "game_id": game_id,
                    "unique_game_id": unique_id,
                    "team1": team1_display,
                    "team2": team2_display,
                    "winner": winner_display
                }
                
                # Only include region for rounds before the Final Four
                if round_num < 5 or (round_num == 5 and region != "Championship"):
                    matchup_data["region"] = region
                
                export_data[round_name].append(matchup_data)
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Bracket exported to {filepath}")

def main() -> None:
    """Main function to run the bracket prediction."""
    predictor = BracketPredictor(randomness_factor=0.1)
    
    # Load data - either from files or manual input
    elo_file = input("Enter path to ELO ratings file (or press Enter to skip): ").strip()
    teams_data = None
    if elo_file:
        teams_data = predictor.load_elo_ratings(elo_file)
    else:
        print("You'll need to provide team ELO data manually.")
    
    bracket_file = input("Enter path to bracket file (or press Enter to skip): ").strip()
    if bracket_file:
        predictor.load_tournament_bracket(bracket_file)
    
    # If we don't have complete team data yet, allow manual entry
    if not teams_data or not all(key in teams_data[0] for key in ["name", "seed", "elo", "region"]):
        print("\nEnter team information manually (empty name to finish):")
        teams_data = []
        
        regions = ["East", "West", "South", "Midwest"]
        print(f"Regions: {', '.join(regions)}")
        
        while True:
            name = input("\nTeam name (or press Enter to finish): ").strip()
            if not name:
                break
                
            seed = int(input("Seed (1-16): ").strip())
            elo = float(input("ELO rating: ").strip())
            
            print("Regions: " + ", ".join(regions))
            region = input("Region: ").strip()
            
            teams_data.append({
                "name": name,
                "seed": seed,
                "elo": elo,
                "region": region
            })
        
        if teams_data:
            predictor.setup_first_round(teams_data)
    
    # Simulate tournament
    results = predictor.simulate_tournament()
    
    # Print and export results
    predictor.print_bracket(results)
    
    export_file = input("\nEnter filename to export bracket (or press Enter to skip): ").strip()
    if export_file:
        predictor.export_bracket(results, export_file)

if __name__ == "__main__":
    main() 