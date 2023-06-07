import re
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime, timedelta
from pybaseball.datasources.bref import BRefSession
from bs4 import BeautifulSoup
from unidecode import unidecode
from pybaseball import statcast_batter, playerid_lookup, batting_stats, playerid_reverse_lookup, team_game_logs

today = datetime.today()
yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
two_weeks_ago = (today - timedelta(days=14)).strftime('%Y-%m-%d')
players_overdue = []
problem_players = []

def get_current_team(player):
    key = player['key_fangraphs'][0]
    url = f'https://www.fangraphs.com/players/player-name/{key}/stats'
    session = BRefSession()
    response = session.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    header = soup.find_all('div', {'class': 'player-info-box-header'})[0]
    return header['data-team-color']

def main():
  columns=['Name', 'Team', 'Age', 'G', 'AB', 'PA', 'HR', 'OBP', 'SLG', 'ISO', 'FB', 'HR/FB', 'Pull%', 'Cent%', 'Oppo%', 'Hard%', 'OBP+', 'SLG+', 'ISO+', 'FB%+', 'HR/FB%+', 'Pull%+', 'Cent%+', 'Oppo%+', 'Hard%+', 'Barrels', 'Barrel%', 'HardHit%', 'HR%', 'HR-every-X-PA']
  bs = batting_stats(2019, end_season=2023, qual=500, ind=0)
  bs['HR%'] = bs.apply(lambda row: row['HR']/row['PA'], axis=1)
  filtered = bs[bs['Age'] < 32].copy()
  sorted_bs = filtered.sort_values(by='HR%', ascending=False).head(200)
  sorted_bs['HR-every-X-PA'] = sorted_bs.apply(lambda row: 1/row['HR%'], axis=1)
  main_df = sorted_bs[columns].copy()
  main_df['Overdue'] = False
  main_df = main_df.sort_values(by="HR", ascending=False).head(75).sort_values(by="HR%", ascending=False).head(50)
  team_avg_PA_per_game = {}
  team_abbr = ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET', 
             'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK', 
             'PHI', 'PIT', 'SDP', 'SEA', 'SFG', 'STL', 'TEX', 'TBR', 'TOR', 'WSN']
  for team in tqdm(team_abbr):
    game_logs = team_game_logs(season=2023, team=team)
    num_of_games_played = game_logs.tail(1)
    avg_PA_per_game = (game_logs['PA'].sum()/game_logs.tail(1)['Game'].iloc[0])/9
    team_avg_PA_per_game[team] = avg_PA_per_game
  for idx, row in main_df.iterrows():
    name_parts = row['Name'].split()
    first_name = name_parts[0]
    last_name = name_parts[1]
    print(f"Getting stats for {first_name} {last_name}")
    
    try:
      #can probably use player_search_list outside of this loop to optimize
      player_id = playerid_lookup(last_name, first_name, True).head(1)['key_mlbam'][0]
      player = playerid_reverse_lookup([player_id])

      if unidecode(player['name_last'][0].lower()) != unidecode(last_name.lower()) or unidecode(player['name_first'][0].lower()) != unidecode(first_name.lower()):
          #need to deal with accents
          print(f'something wrong with player {first_name} {last_name}')
          name = first_name + ' ' + last_name
          problem_players.append(name)
          continue

      statcast = statcast_batter(start_dt=two_weeks_ago, end_dt=yesterday, player_id=player_id)
      if len(statcast) == 0:
          #mark as not in league
  #         print('not in league')
          continue

      most_recent_homer = statcast[statcast['events']=='home_run']
      if most_recent_homer.empty:
  #         print(f'#{first_name} #{last_name} is overdue')
          row['Overdue'] = True
          continue
      most_recent_homer_date = most_recent_homer.reset_index().head(1)['game_date'][0]
      parsed_date = datetime.strptime(most_recent_homer_date, "%Y-%m-%d").strftime("%b %-d")
      escaped_date_string = re.escape(parsed_date)

      pattern = f"^{escaped_date_string}.*$"

      current_team = get_current_team(player)
      logs = team_game_logs(season=2023, team=current_team)[::-1].reset_index()
      homered_this_many_games_ago = logs[logs['Date'].str.match(pattern)].index[0] + 1
      estimated_plate_appearances_since_last_homer = homered_this_many_games_ago * team_avg_PA_per_game[current_team]
      if estimated_plate_appearances_since_last_homer >= row['HR-every-X-PA']:
  #         print(f'#{first_name} #{last_name} is overdue ha')
          main_df.loc[idx, 'Overdue'] = True
      else:
          main_df.loc[idx, 'Overdue'] = False
    except:
        print('failed. skipping')
        main_df.loc[idx, 'Overdue'] = False
  overdue = main_df[main_df['Overdue'] == True]
  print(overdue)

if __name__ == "__main__":
    main()