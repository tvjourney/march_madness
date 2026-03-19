#!/usr/bin/env python3
"""
March Madness Bracket Predictor

This script predicts a March Madness tournament bracket based on ELO ratings with 10% randomness.
It obtains ELO ratings from data sources, processes the tournament bracket, and simulates matchups.
"""

import pandas as pd
import random
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
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
    # Advanced stats (KenPom-equivalent from barttorvik.com T-Rank)
    adj_oe: Optional[float] = None   # Adjusted offensive efficiency (points per 100 possessions)
    adj_de: Optional[float] = None   # Adjusted defensive efficiency (points allowed per 100)
    adj_t: Optional[float] = None    # Adjusted tempo (possessions per 40 minutes)
    net_rtg: Optional[float] = None  # Net rating = adj_oe - adj_de

    def __post_init__(self) -> None:
        if self.net_rtg is None and self.adj_oe is not None and self.adj_de is not None:
            self.net_rtg = self.adj_oe - self.adj_de

    def __str__(self) -> str:
        if self.net_rtg is not None:
            return f"{self.seed}. {self.name} (ELO: {self.elo:.0f}, NetRtg: {self.net_rtg:+.1f})"
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
    
    def win_probability(self) -> float:
        """
        Compute team1's win probability using available data.

        Blends ELO-based probability with efficiency-based probability when
        advanced stats (AdjOE / AdjDE) are present.  The ELO formula is the
        standard chess/538 log5 model; the efficiency model uses a logistic
        curve calibrated so that a +10 net-rating gap ≈ 75% win probability
        (consistent with KenPom historical calibration).

        Returns:
            Probability that team1 wins (0–1).
        """
        # ELO win probability (standard formula)
        elo_diff = self.team1.elo - self.team2.elo
        p_elo = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))

        # If both teams have advanced stats, blend in efficiency probability
        t1_net = self.team1.net_rtg
        t2_net = self.team2.net_rtg
        if t1_net is not None and t2_net is not None:
            net_diff = t1_net - t2_net
            # logistic scale k=0.15 → net_diff of ~10 pts ≈ 75% win prob
            p_eff = 1.0 / (1.0 + math.exp(-0.15 * net_diff))
            # Weight: 40% ELO, 60% efficiency (advanced stats are more predictive)
            return 0.4 * p_elo + 0.6 * p_eff

        return p_elo

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
        Simulate matchup using a win probability model blended with seed-calibrated noise.

        The base win probability comes from win_probability() (ELO ± advanced stats).
        Noise is then applied via a seed-matchup-specific randomness factor derived from
        historical NCAA upset rates, making the simulation more realistic than a flat
        ELO perturbation.

        Returns:
            The winning Team object
        """
        # Base win probability from model (ELO + advanced stats)
        p_team1 = self.win_probability()

        # Seed matchup context
        higher_seed = min(self.team1.seed, self.team2.seed)
        lower_seed = max(self.team1.seed, self.team2.seed)

        if self.round_num == 1:
            # Noise levels calibrated to historical first-round upset rates
            noise_map = {
                (1, 16): 0.03,   # ~1.3% upset rate
                (2, 15): 0.10,   # ~7.1%
                (3, 14): 0.15,   # ~14.7%
                (4, 13): 0.18,   # ~20.5%
                (5, 12): 0.27,   # ~35.3% — the famous 12-seed
                (6, 11): 0.30,   # ~39.1%
                (7, 10): 0.30,   # ~38.7%
                (8,  9): 0.40,   # ~51.9% — nearly a coin flip
            }
            noise = noise_map.get((higher_seed, lower_seed), 0.20)
            # Perturb the win probability symmetrically
            p_team1 += random.uniform(-noise, noise)
        else:
            # Later rounds: noise shrinks for top seeds as they prove themselves
            def get_noise(seed: int, rnd: int) -> float:
                if seed == 1:
                    return max(0.05, 0.20 - (rnd - 1) * 0.04)
                elif seed == 2:
                    return max(0.08, 0.20 - (rnd - 1) * 0.03)
                elif seed <= 4:
                    return max(0.12, 0.20 - (rnd - 1) * 0.02)
                elif seed <= 8:
                    return max(0.15, 0.20 - (rnd - 1) * 0.01)
                else:
                    # Cinderella teams that survive keep surprising
                    return min(0.40, 0.20 + (rnd - 1) * 0.05)

            n1 = get_noise(self.team1.seed, self.round_num)
            n2 = get_noise(self.team2.seed, self.round_num)
            # Average the two noise levels, then perturb
            noise = (n1 + n2) / 2.0
            p_team1 += random.uniform(-noise, noise)

            # Championship: small historical boost for #1 seeds (64.1% title win rate)
            if self.round_num == 6:
                if self.team1.seed == 1:
                    p_team1 += 0.05
                if self.team2.seed == 1:
                    p_team1 -= 0.05

        # Clamp to [0, 1] and draw outcome
        p_team1 = max(0.0, min(1.0, p_team1))
        return self.team1 if random.random() < p_team1 else self.team2
    
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
                region=team_info["region"],
                adj_oe=team_info.get("adj_oe"),
                adj_de=team_info.get("adj_de"),
                adj_t=team_info.get("adj_t"),
                net_rtg=team_info.get("net_rtg"),
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
    
    def simulate_n_times(self, n: int = 1000) -> Dict[str, Any]:
        """
        Run the full tournament simulation n times and aggregate win probabilities.

        Each simulation is independent.  The results include, for every team,
        how often they reach each round and win the championship.

        Args:
            n: Number of simulations to run (default 1000).

        Returns:
            Dictionary with keys:
              - "simulations": n (int)
              - "champion_prob": {team_name: probability} sorted descending
              - "round_reach_prob": {round_name: {team_name: probability}}
        """
        from collections import defaultdict

        champion_counts: Dict[str, int] = defaultdict(int)
        round_reach_counts: Dict[int, Dict[str, int]] = {
            r: defaultdict(int) for r in range(1, 7)
        }

        print(f"Running {n} tournament simulations...")
        for _ in range(n):
            results = self.simulate_tournament()
            for round_num, matchups in results.items():
                for team1, team2, winner, region, game_id, unique_id in matchups:
                    # Both teams reached this round
                    if not team1.is_tbd:
                        round_reach_counts[round_num][team1.name] += 1
                    if not team2.is_tbd:
                        round_reach_counts[round_num][team2.name] += 1
                    # Championship winner
                    if round_num == 6 and not winner.is_tbd:
                        champion_counts[winner.name] += 1

        champion_prob = {
            name: round(count / n, 4)
            for name, count in sorted(champion_counts.items(), key=lambda x: -x[1])
        }

        round_reach_prob: Dict[str, Dict[str, float]] = {}
        for round_num, counts in round_reach_counts.items():
            round_name = self.round_names.get(round_num, f"Round {round_num}")
            round_reach_prob[round_name] = {
                name: round(count / n, 4)
                for name, count in sorted(counts.items(), key=lambda x: -x[1])
            }

        return {
            "simulations": n,
            "champion_prob": champion_prob,
            "round_reach_prob": round_reach_prob,
        }

    def export_simulation_results(self, sim_results: Dict[str, Any], filepath: str) -> None:
        """
        Export multi-simulation probability results to a JSON file.

        Args:
            sim_results: Output of simulate_n_times().
            filepath: Path to write JSON output.
        """
        with open(filepath, "w") as f:
            json.dump(sim_results, f, indent=2)
        print(f"Simulation probabilities exported to {filepath}")

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