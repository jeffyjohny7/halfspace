# Realism report

**43 of 43** league-level checks inside real-football ranges (top division, 2025-26, full season).

Ranges are approximate figures for a modern top-flight league and are deliberately wide.

| Check | Synthetic | Real-world range | |
|---|---|---|---|
| Goals per match | 2.892 | 2.5 - 3.2 | pass |
| Home win rate | 0.432 | 0.4 - 0.49 | pass |
| Draw rate | 0.245 | 0.2 - 0.3 | pass |
| Away win rate | 0.324 | 0.26 - 0.36 | pass |
| Shots per match | 25.7 | 22.0 - 28.5 | pass |
| Share of shots on target | 0.334 | 0.3 - 0.38 | pass |
| xG per shot | 0.106 | 0.09 - 0.13 | pass |
| Goals per shot | 0.108 | 0.09 - 0.13 | pass |
| Share of shots from outside the box | 0.422 | 0.28 - 0.45 | pass |
| Passes per match | 1050.2 | 850.0 - 1100.0 | pass |
| Pass completion | 0.806 | 0.78 - 0.86 | pass |
| Corners per match | 9.503 | 8.5 - 11.5 | pass |
| Fouls per match | 20.0 | 17.0 - 24.0 | pass |
| Yellow cards per match | 3.987 | 3.0 - 4.8 | pass |
| Red cards per match | 0.113 | 0.04 - 0.22 | pass |
| Penalties per match | 0.266 | 0.18 - 0.36 | pass |
| Penalty conversion | 0.752 | 0.68 - 0.86 | pass |
| Offsides per match | 3.542 | 2.5 - 5.0 | pass |
| Share of goals from set pieces (incl. penalties) | 0.278 | 0.2 - 0.34 | pass |
| Share of goals scored after the 75th minute | 0.258 | 0.17 - 0.3 | pass |
| Added time, first half (min) | 3.818 | 1.5 - 6.0 | pass |
| Added time, second half (min) | 9.061 | 4.0 - 10.0 | pass |
| Champion's points (38 games) | 91.0 | 75.0 - 100.0 | pass |
| 17th place points | 35.0 | 30.0 - 42.0 | pass |
| Bottom club's points | 32.0 | 10.0 - 35.0 | pass |
| Highest season possession share | 0.596 | 0.55 - 0.67 | pass |
| Lowest season possession share | 0.412 | 0.33 - 0.45 | pass |
| Passes per 90, centre-backs | 44.8 | 40.0 - 75.0 | pass |
| Passes per 90, full-backs | 41.0 | 32.0 - 65.0 | pass |
| Passes per 90, central and defensive midfielders | 64.0 | 42.0 - 80.0 | pass |
| Passes per 90, wingers | 37.7 | 22.0 - 48.0 | pass |
| Passes per 90, strikers | 29.5 | 15.0 - 36.0 | pass |
| Passes per 90, goalkeepers | 20.4 | 16.0 - 40.0 | pass |
| Injuries per club per season | 28.4 | 16.0 - 45.0 | pass |
| Average days out per injury | 18.9 | 10.0 - 35.0 | pass |
| Players injured or suspended per club per match | 1.411 | 1.0 - 5.0 | pass |
| Suspensions per club per season | 5.150 | 1.0 - 8.0 | pass |
| Top scorer's league goals | 34.0 | 20.0 - 37.0 | pass |
| Most league assists | 17.0 | 10.0 - 22.0 | pass |
| Biggest finishing overperformance (goals minus xG) | 9.676 | 0.0 - 12.0 | pass |
| Shots per 90, strikers | 2.664 | 1.8 - 3.4 | pass |
| Shots per 90, wingers | 1.734 | 1.2 - 3.0 | pass |
| Most shots per 90 (1,500+ minutes) | 4.678 | 3.0 - 5.5 | pass |

## Do the hidden truths show up in the data?

For every planted trait we measure the matching statistic and compare it with peers (same position for players, same division for teams). *Detectable* means at least one standard deviation away from peers in the expected direction, on a usable sample.

- Previous season (2025-26, full season): **78/99** planted traits detectable
- Current season (2026-27, rounds played so far): **34/60** - smaller sample, so the Scout should also use last season's data.

### 2025-26

| Club | Player | Trait | Metric | Value | Peer mean | z | Detectable |
|---|---|---|---|---|---|---|---|
| Lowmarsh Harriers |  | set_piece_attack_strong | sp_xg_per_match | 0.455 | 0.249 | 6.060 | yes |
| Lowmarsh Harriers | Adam Vesodrez | clinical_finisher | goals_minus_xg_per_shot | -0.029 | 0.012 | -0.930 | no |
| Lowmarsh Harriers | Malik Olotez | loses_ball_under_pressure | disp_per_press | 0.190 | 0.065 | 5.340 | yes |
| Dunvarrow Borough |  | set_piece_attack_strong | sp_xg_per_match | 0.435 | 0.249 | 5.550 | yes |
| Dunvarrow Borough |  | left_flank_focus | left_entry_share | 0.514 | 0.350 | 2.020 | yes |
| Dunvarrow Borough | Emil Varailo | loses_ball_under_pressure | disp_per_press | 0.175 | 0.095 | 2.740 | yes |
| Wyncaster County |  | set_piece_attack_strong | sp_xg_per_match | 0.315 | 0.249 | 2.490 | yes |
| Wyncaster County |  | left_flank_focus | left_entry_share | 0.527 | 0.350 | 2.150 | yes |
| Wyncaster County | Emil Darham | press_resistant_playmaker | disp_per_press | 0.024 | 0.065 | -1.330 | yes |
| Wyncaster County | Nils Salevuba | clinical_finisher | goals_minus_xg_per_shot | 0.027 | -0.009 | 1.260 | yes |
| Highcrest Rangers |  | late_fade | late_xga_ratio | 1.490 | 1.560 | -0.070 | no |
| Highcrest Rangers | Leo Marimere | weak_in_the_air | aerial_win_rate | 0.345 | 0.686 | -4.260 | yes |
| Gallowmere Albion |  | fortress_home | home_minus_away_xgd | 0.669 | 0.489 | 1.400 | yes |
| Gallowmere Albion | Jordan Mareell | loses_ball_under_pressure | disp_per_press | 0.268 | 0.095 | 5.440 | yes |
| Gallowmere Albion | Elias Delarino | hothead | fouls_cards_per90 | 1.940 | 1.208 | 1.100 | yes |
| Stonemarsh Albion |  | left_flank_focus | left_entry_share | 0.524 | 0.350 | 2.130 | yes |
| Stonemarsh Albion |  | fortress_home | home_minus_away_xgd | 0.607 | 0.489 | 0.900 | no |
| Stonemarsh Albion | Stellan Korino | goalkeeper_weak_on_crosses | claims_per90 | 0.245 | 2.384 | -2.560 | yes |
| Ravenholt City |  | set_piece_defense_weak | sp_xga_per_match | 0.356 | 0.249 | 1.540 | yes |
| Ravenholt City |  | left_flank_focus | left_entry_share | 0.522 | 0.350 | 2.100 | yes |
| Ravenholt City | Omar Halovik | goalkeeper_weak_on_crosses | claims_per90 | 0.407 | 2.384 | -2.390 | yes |
| Ravenholt City | Hugo Berodrez | loses_ball_under_pressure | disp_per_press | 0.218 | 0.068 | 8.060 | yes |
| Ironvale Rangers |  | set_piece_defense_weak | sp_xga_per_match | 0.336 | 0.249 | 1.270 | yes |
| Ironvale Rangers | Nils Kelumenko | loses_ball_under_pressure | disp_per_press | 0.216 | 0.095 | 3.930 | yes |
| Corrowby Rangers |  | fortress_home | home_minus_away_xgd | 0.627 | 0.489 | 1.070 | yes |
| Corrowby Rangers | Elias Delerez | error_prone_passer | completion_over_expected | -0.195 | 0.023 | -4.870 | yes |
| Corrowby Rangers | Ben Jaruema | clinical_finisher | goals_minus_xg_per_shot | 0.056 | -0.001 | 1.730 | yes |
| Duncliffe Albion |  | late_fade | late_xga_ratio | 1.562 | 1.560 | 0.190 | no |
| Duncliffe Albion |  | left_flank_focus | left_entry_share | 0.546 | 0.350 | 2.340 | yes |
| Duncliffe Albion | Emeka Morndo | clinical_finisher | goals_minus_xg_per_shot | 0.027 | 0.012 | 0.490 | no |
| Cragmouth County |  | poor_discipline | fouls_per_match | 17.1 | 9.976 | 4.220 | yes |
| Cragmouth County | Jonas Tamequist | weak_in_the_air | aerial_win_rate | 0.483 | 0.686 | -2.670 | yes |
| Calderwyn Town |  | late_fade | late_xga_ratio | 1.391 | 1.560 | -0.430 | no |
| Calderwyn Town | Kofi Adoley | hothead | fouls_cards_per90 | 2.978 | 1.164 | 3.670 | yes |
| Quarlston Rangers |  | right_flank_focus | right_entry_share | 0.545 | 0.345 | 1.410 | yes |
| Quarlston Rangers | Milan Zelcott | goalkeeper_weak_on_crosses | claims_per90 | 0.534 | 2.384 | -2.260 | yes |
| Mistlecombe Town |  | fortress_home | home_minus_away_xgd | 0.471 | 0.489 | -0.190 | no |
| Mistlecombe Town | Mateo Dunevwick | elite_crosser | cross_completion | 0.267 | 0.235 | 0.390 | no |
| Mistlecombe Town | David Yaribore | hothead | fouls_cards_per90 | 1.198 | 1.067 | 0.000 | no |
| Ashbrook Vale Rovers |  | right_flank_focus | right_entry_share | 0.592 | 0.345 | 1.760 | yes |
| Ashbrook Vale Rovers |  | fortress_home | home_minus_away_xgd | 0.485 | 0.489 | -0.080 | no |
| Ashbrook Vale Rovers | Jakub Delanley | hothead | fouls_cards_per90 | 2.046 | 0.717 | 3.840 | yes |
| Ashbrook Vale Rovers | Sebastian Delanberg | error_prone_passer | completion_over_expected | -0.197 | 0.059 | -6.490 | yes |
| Varnholm FC |  | left_flank_focus | left_entry_share | 0.533 | 0.350 | 2.210 | yes |
| Varnholm FC | Leo Falaberg | weak_in_the_air | aerial_win_rate | 0.367 | 0.686 | -4.010 | yes |
| Varnholm FC | Zane Pelibnov | elite_crosser | cross_completion | 0.235 | 0.235 | 0.000 | no |
| Penmarrow Athletic |  | poor_discipline | fouls_per_match | 15.9 | 9.976 | 3.560 | yes |
| Penmarrow Athletic |  | fortress_home | home_minus_away_xgd | 0.696 | 0.489 | 1.620 | yes |
| Penmarrow Athletic | Santiago Sevanford | loses_ball_under_pressure | disp_per_press | 0.222 | 0.095 | 4.110 | yes |
| Penmarrow Athletic | Ali Yararzak | weak_in_the_air | aerial_win_rate | 0.320 | 0.686 | -4.550 | yes |
| Hollowmere Rovers |  | set_piece_attack_strong | sp_xg_per_match | 0.217 | 0.249 | -0.030 | no |
| Hollowmere Rovers | Dev Fenola | elite_crosser | cross_completion | 0.404 | 0.227 | 1.650 | yes |
| Hollowmere Rovers | Jonas Calennov | error_prone_passer | completion_over_expected | -0.154 | 0.023 | -4.020 | yes |
| Elderbridge City |  | right_flank_focus | right_entry_share | 0.565 | 0.345 | 1.560 | yes |
| Elderbridge City |  | fortress_home | home_minus_away_xgd | 0.264 | 0.489 | -1.860 | no |
| Elderbridge City | Hamza Ulibell | press_resistant_playmaker | disp_per_press | 0.029 | 0.065 | -1.130 | yes |
| Elderbridge City | Aurelio Darilard | goalkeeper_weak_on_crosses | claims_per90 | 0.354 | 2.384 | -2.440 | yes |
| Oxmere County |  | set_piece_attack_strong | sp_xg_per_match | 0.267 | 0.249 | 1.250 | yes |
| Oxmere County |  | high_line_exposed | opp_offsides_per_match | 2.316 | 1.771 | 1.350 | yes |
| Oxmere County | Jonas Admere | weak_in_the_air | aerial_win_rate | 0.292 | 0.686 | -4.870 | yes |
| Grimsforth City | Sven Wilson | error_prone_passer | completion_over_expected | -0.183 | 0.011 | -5.250 | yes |
| Fennholt FC |  | right_flank_focus | right_entry_share | 0.531 | 0.347 | 2.780 | yes |
| Fennholt FC | Joel Moriric | elite_crosser | cross_completion | 0.396 | 0.183 | 3.180 | yes |
| Breckhaven City | Ivan Ikodmere | weak_in_the_air | aerial_win_rate | 0.554 | 0.709 | -2.190 | yes |
| Kestrelford Athletic | Daniel Adorema | elite_crosser | cross_completion | 0.400 | 0.208 | 3.100 | yes |
| Wrenfield Harriers | Andre Fenumgard | loses_ball_under_pressure | disp_per_press | 0.214 | 0.070 | 6.350 | yes |
| Harrowdeen Athletic |  | set_piece_defense_weak | sp_xga_per_match | 0.333 | 0.187 | 3.170 | yes |
| Harrowdeen Athletic | Santiago Mareveke | error_prone_passer | completion_over_expected | -0.190 | -0.077 | -1.890 | yes |
| Pellmoor Borough |  | fortress_home | home_minus_away_xgd | 0.294 | 0.169 | 0.600 | no |
| Pellmoor Borough | Callum Naligard | error_prone_passer | completion_over_expected | -0.185 | -0.077 | -1.810 | yes |
| Vexley Cross Harriers |  | left_flank_focus | left_entry_share | 0.514 | 0.338 | 2.400 | yes |
| Vexley Cross Harriers | Diego Belani | loses_ball_under_pressure | disp_per_press | 0.223 | 0.079 | 6.530 | yes |
| Saltmere Athletic |  | set_piece_defense_weak | sp_xga_per_match | 0.370 | 0.187 | 3.920 | yes |
| Saltmere Athletic | Caleb Ikcott | goalkeeper_weak_on_crosses | claims_per90 | 0.533 | 1.871 | -1.910 | yes |
| Marrowgate Borough |  | late_fade | late_xga_ratio | 1.246 | 1.538 | -1.340 | no |
| Marrowgate Borough | Gabriel Delumard | weak_in_the_air | aerial_win_rate | 0.425 | 0.709 | -3.920 | yes |
| Morrowdene Wanderers |  | high_line_exposed | opp_offsides_per_match | 2.304 | 1.768 | 1.570 | yes |
| Morrowdene Wanderers | Eric Branemere | clinical_finisher | goals_minus_xg_per_shot | 0.033 | 0.020 | 0.420 | no |
| Kelvarth County |  | set_piece_defense_weak | sp_xga_per_match | 0.251 | 0.187 | 1.540 | yes |
| Kelvarth County | Nathan Tamric | press_resistant_playmaker | disp_per_press | 0.040 | 0.080 | -1.910 | yes |
| Larkspur Bay County |  | left_flank_focus | left_entry_share | 0.513 | 0.338 | 2.370 | yes |
| Larkspur Bay County | Arlo Lorilici | press_resistant_playmaker | disp_per_press | 0.032 | 0.070 | -1.400 | yes |
| Coldwyke FC |  | late_fade | late_xga_ratio | 1.652 | 1.538 | 0.570 | no |
| Coldwyke FC | Ethan Delarley | loses_ball_under_pressure | disp_per_press | 0.131 | 0.088 | 1.580 | yes |
| Rookhaven Borough |  | fortress_home | home_minus_away_xgd | 0.451 | 0.169 | 1.240 | yes |
| Rookhaven Borough | Marco Ishienko | weak_in_the_air | aerial_win_rate | 0.535 | 0.709 | -2.450 | yes |
| Sedgecombe Athletic | Adam Pelarwell | error_prone_passer | completion_over_expected | -0.168 | 0.011 | -4.860 | yes |
| Swanmoor Albion |  | set_piece_defense_weak | sp_xga_per_match | 0.216 | 0.187 | 0.840 | no |
| Swanmoor Albion | Lucas Olodyi | loses_ball_under_pressure | disp_per_press | 0.134 | 0.088 | 1.660 | yes |
| Ambershaw United | Hamza Gilibrez | loses_ball_under_pressure | disp_per_press | 0.166 | 0.088 | 2.670 | yes |
| Torvale United | Javier Calby | goalkeeper_weak_on_crosses | claims_per90 | 0.505 | 1.871 | -1.950 | yes |
| Fairhollow Athletic | Theo Ikodndo | weak_in_the_air | aerial_win_rate | 0.523 | 0.709 | -2.600 | yes |
| Thistlewick United |  | left_flank_focus | left_entry_share | 0.528 | 0.338 | 2.590 | yes |
| Thistlewick United | Milan Ulenzak | clinical_finisher | goals_minus_xg_per_shot | 0.023 | 0.008 | 0.220 | no |
| Glimmerstone Borough |  | right_flank_focus | right_entry_share | 0.530 | 0.347 | 2.770 | yes |
| Glimmerstone Borough | Declan Ishieke | elite_crosser | cross_completion | 0.343 | 0.196 | 1.310 | yes |
| Briarstead Rovers |  | late_fade | late_xga_ratio | 1.333 | 1.538 | -0.930 | no |
| Briarstead Rovers | Musa Sevorson | clinical_finisher | goals_minus_xg_per_shot | -0.014 | 0.004 | -0.660 | no |
| Blackmire Athletic | Tomas Halney | elite_crosser | cross_completion | 0.377 | 0.196 | 1.620 | yes |

### 2026-27 (so far)

| Club | Player | Trait | Metric | Value | Peer mean / before | z / change | Detectable |
|---|---|---|---|---|---|---|---|
| Lowmarsh Harriers |  | set_piece_attack_strong | sp_xg_per_match | 0.360 | 0.270 | 1.150 | yes |
| Lowmarsh Harriers | Adam Vesodrez | clinical_finisher | goals_minus_xg_per_shot | 0.044 | 0.039 | -0.090 | no |
| Lowmarsh Harriers | Malik Olotez | loses_ball_under_pressure | disp_per_press | 0.174 | 0.065 | 4.800 | yes |
| Dunvarrow Borough |  | set_piece_attack_strong | sp_xg_per_match | 0.594 | 0.270 | 3.910 | yes |
| Dunvarrow Borough |  | left_flank_focus | left_entry_share | 0.489 | 0.366 | 1.100 | yes |
| Dunvarrow Borough | Emil Varailo | loses_ball_under_pressure | disp_per_press | 0.262 | 0.094 | 3.610 | yes |
| Wyncaster County |  | set_piece_attack_strong | sp_xg_per_match | 0.262 | 0.270 | -0.010 | no |
| Wyncaster County |  | left_flank_focus | left_entry_share | 0.550 | 0.366 | 1.550 | yes |
| Wyncaster County | Emil Darham | press_resistant_playmaker | disp_per_press | 0.046 | 0.065 | -0.590 | no |
| Wyncaster County | Nils Salevuba | clinical_finisher | goals_minus_xg_per_shot | -0.085 | -0.016 | -1.880 | no |
| Highcrest Rangers |  | late_fade | late_xga_ratio | 1.385 | 1.732 | -0.260 | no |
| Highcrest Rangers | Leo Marimere | weak_in_the_air | aerial_win_rate | 0.417 | 0.683 | -2.820 | yes |
| Gallowmere Albion |  | fortress_home | home_minus_away_xgd | 0.976 | 0.494 | 0.730 | no |
| Gallowmere Albion | Jordan Mareell | loses_ball_under_pressure | disp_per_press | 0.132 | 0.094 | 1.020 | yes |
| Gallowmere Albion | Elias Delarino | hothead | fouls_cards_per90 | 2.318 | 1.512 | 1.120 | yes |
| Stonemarsh Albion |  | left_flank_focus | left_entry_share | 0.532 | 0.366 | 1.420 | yes |
| Stonemarsh Albion |  | fortress_home | home_minus_away_xgd | 1.107 | 0.494 | 0.920 | no |
| Stonemarsh Albion | Stellan Korino | goalkeeper_weak_on_crosses | claims_per90 | 0.000 | 2.474 | -2.180 | yes |
| Ravenholt City |  | set_piece_defense_weak | sp_xga_per_match | 0.408 | 0.270 | 0.980 | no |
| Ravenholt City |  | left_flank_focus | left_entry_share | 0.497 | 0.366 | 1.160 | yes |
| Ravenholt City | Omar Halovik | goalkeeper_weak_on_crosses | claims_per90 | 0.455 | 2.474 | -1.810 | yes |
| Ravenholt City | Hugo Berodrez | loses_ball_under_pressure | disp_per_press | 0.302 | 0.068 | 6.720 | yes |
| Ironvale Rangers |  | set_piece_defense_weak | sp_xga_per_match | 0.124 | 0.270 | -0.930 | no |
| Ironvale Rangers | Nils Kelumenko | loses_ball_under_pressure | disp_per_press | 0.211 | 0.094 | 2.590 | yes |
| Corrowby Rangers |  | fortress_home | home_minus_away_xgd | -0.008 | 0.494 | -0.730 | no |
| Corrowby Rangers | Elias Delerez | error_prone_passer | completion_over_expected | -0.189 | 0.016 | -4.680 | yes |
| Corrowby Rangers | Ben Jaruema | clinical_finisher | goals_minus_xg_per_shot | 0.069 | -0.018 | 3.500 | yes |
| Duncliffe Albion |  | late_fade | late_xga_ratio | 1.157 | 1.732 | -0.650 | no |
| Duncliffe Albion |  | left_flank_focus | left_entry_share | 0.542 | 0.366 | 1.490 | yes |
| Duncliffe Albion | Emeka Morndo | clinical_finisher | goals_minus_xg_per_shot | - | 0.039 | - | no |
| Cragmouth County |  | poor_discipline | fouls_per_match | 19.5 | 10.4 | 5.370 | yes |
| Cragmouth County | Jonas Tamequist | weak_in_the_air | aerial_win_rate | 0.467 | 0.683 | -2.360 | yes |
| Quarlston Rangers |  | right_flank_focus | right_entry_share | 0.541 | 0.324 | 1.330 | yes |
| Quarlston Rangers | Milan Zelcott | goalkeeper_weak_on_crosses | claims_per90 | - | - | - | no |
| Mistlecombe Town |  | fortress_home | home_minus_away_xgd | 0.421 | 0.494 | -0.090 | no |
| Mistlecombe Town | Mateo Dunevwick | elite_crosser | cross_completion | 0.188 | 0.244 | -0.720 | no |
| Mistlecombe Town | David Yaribore | hothead | fouls_cards_per90 | 1.843 | 1.284 | 0.750 | no |
| Varnholm FC |  | left_flank_focus | left_entry_share | 0.533 | 0.366 | 1.420 | yes |
| Varnholm FC | Leo Falaberg | weak_in_the_air | aerial_win_rate | 0.268 | 0.683 | -4.180 | yes |
| Varnholm FC | Zane Pelibnov | elite_crosser | cross_completion | 0.111 | 0.244 | -1.430 | no |
| Penmarrow Athletic |  | poor_discipline | fouls_per_match | 15.9 | 10.4 | 3.430 | yes |
| Penmarrow Athletic |  | fortress_home | home_minus_away_xgd | 0.616 | 0.494 | 0.190 | no |
| Penmarrow Athletic | Santiago Sevanford | loses_ball_under_pressure | disp_per_press | 0.115 | 0.094 | 0.670 | no |
| Penmarrow Athletic | Ali Yararzak | weak_in_the_air | aerial_win_rate | 0.484 | 0.683 | -2.200 | yes |
| Hollowmere Rovers |  | set_piece_attack_strong | sp_xg_per_match | 0.145 | 0.270 | -1.390 | no |
| Hollowmere Rovers | Dev Fenola | elite_crosser | cross_completion | 0.308 | 0.203 | 0.900 | no |
| Hollowmere Rovers | Jonas Calennov | error_prone_passer | completion_over_expected | -0.140 | 0.016 | -3.720 | yes |
| Oxmere County |  | set_piece_attack_strong | sp_xg_per_match | 0.288 | 0.270 | 0.300 | no |
| Oxmere County |  | high_line_exposed | opp_offsides_per_match | 2.400 | 1.945 | 0.670 | no |
| Oxmere County | Jonas Admere | weak_in_the_air | aerial_win_rate | 0.400 | 0.683 | -2.970 | yes |
| Grimsforth City | Sven Wilson | error_prone_passer | completion_over_expected | -0.192 | 0.064 | -5.320 | yes |
| Fennholt FC |  | right_flank_focus | right_entry_share | 0.599 | 0.324 | 1.710 | yes |
| Fennholt FC | Joel Moriric | elite_crosser | cross_completion | 0.222 | 0.241 | 0.250 | no |
| Vexley Cross Harriers |  | left_flank_focus | left_entry_share | 0.514 | 0.366 | 1.290 | yes |
| Vexley Cross Harriers | Diego Belani | loses_ball_under_pressure | disp_per_press | 0.000 | 0.070 | -2.570 | no |
| Highcrest Rangers |  | style_change_press_intensity | pressures_per_opp_pass | 0.296 | 0.216 | 0.081 | yes |
| Highcrest Rangers |  | style_change_directness | long_pass_share | 0.132 | 0.117 | 0.015 | no |
| Gallowmere Albion |  | style_change_press_intensity | pressures_per_opp_pass | 0.298 | 0.224 | 0.075 | yes |
| Gallowmere Albion |  | style_change_directness | long_pass_share | 0.114 | 0.143 | -0.029 | yes |
| Cragmouth County |  | style_change_press_intensity | pressures_per_opp_pass | 0.460 | 0.349 | 0.111 | yes |
| Dunvarrow Borough | Max Ekolund | clinical_finisher (natural) | goals_minus_xg_per_shot | -0.012 | -0.016 | 0.140 | no |
| Dunvarrow Borough | Elias Obeke | clinical_finisher (natural) | goals_minus_xg_per_shot | 0.012 | -0.035 | 1.320 | yes |
| Dunvarrow Borough | Ethan Nalidra | clinical_finisher (natural) | goals_minus_xg_per_shot | 0.101 | 0.039 | 0.860 | no |
| Mistlecombe Town | Anton Raviore | elite_crosser (natural) | cross_completion | 0.200 | 0.264 | -0.940 | no |
| Gallowmere Albion | Sven Lanilici | press_resistant_playmaker (natural) | disp_per_press | 0.018 | 0.065 | -1.810 | yes |
| Stonemarsh Albion | Musa Zelondo | hothead (natural) | fouls_cards_per90 | 1.023 | 1.466 | -0.470 | no |
| Vexley Cross Harriers | Ibrahim Rosortez | hothead (natural) | fouls_cards_per90 | 1.167 | 0.709 | 1.400 | yes |

## League summaries

### Top division 2025-26

| Metric | Value |
|---|---|
| goals_per_match | 2.892 |
| home_win_rate | 0.432 |
| draw_rate | 0.245 |
| away_win_rate | 0.324 |
| shots_per_match | 25.7 |
| on_target_share | 0.334 |
| xg_per_shot | 0.106 |
| goals_per_shot | 0.108 |
| outside_box_shot_share | 0.422 |
| passes_per_match | 1050.2 |
| pass_completion | 0.806 |
| corners_per_match | 9.503 |
| fouls_per_match | 20.0 |
| yellows_per_match | 3.987 |
| reds_per_match | 0.113 |
| penalties_per_match | 0.266 |
| penalty_conversion | 0.752 |
| offsides_per_match | 3.542 |
| set_piece_goal_share | 0.278 |
| late_goal_share | 0.258 |
| added_time_1h | 3.818 |
| added_time_2h | 9.061 |
| max_team_possession | 0.596 |
| min_team_possession | 0.412 |
| champion_points | 91.0 |
| safety_points | 35.0 |
| bottom_points | 32.0 |

### Players and squads 2025-26

| Metric | Value |
|---|---|
| passes_p90_CB | 44.8 |
| passes_p90_FB | 41.0 |
| passes_p90_MID | 64.0 |
| passes_p90_W | 37.7 |
| passes_p90_ST | 29.5 |
| passes_p90_GK | 20.4 |
| top_scorer_goals | 34.0 |
| top_assists | 17.0 |
| top_goals_minus_xg | 9.676 |
| shots_p90_ST | 2.664 |
| shots_p90_W | 1.734 |
| top_shots_p90 | 4.678 |
| injuries_per_club | 28.4 |
| days_out_per_injury | 18.9 |
| match_injury_share | 0.414 |
| suspensions_per_club | 5.150 |
| unavailable_per_match | 1.411 |

### Second tier 2025-26

| Metric | Value |
|---|---|
| goals_per_match | 2.835 |
| home_win_rate | 0.400 |
| draw_rate | 0.237 |
| away_win_rate | 0.362 |
| shots_per_match | 22.5 |
| on_target_share | 0.333 |
| xg_per_shot | 0.107 |
| goals_per_shot | 0.121 |
| outside_box_shot_share | 0.445 |
| passes_per_match | 1050.7 |
| pass_completion | 0.774 |
| corners_per_match | 9.464 |
| fouls_per_match | 19.5 |
| yellows_per_match | 3.971 |
| reds_per_match | 0.072 |
| penalties_per_match | 0.290 |
| penalty_conversion | 0.731 |
| offsides_per_match | 3.536 |
| set_piece_goal_share | 0.259 |
| late_goal_share | 0.219 |
| added_time_1h | 3.989 |
| added_time_2h | 8.993 |
| max_team_possession | 0.587 |
| min_team_possession | 0.414 |

### Top division (rounds so far) 2026-27

| Metric | Value |
|---|---|
| goals_per_match | 2.920 |
| home_win_rate | 0.440 |
| draw_rate | 0.210 |
| away_win_rate | 0.350 |
| shots_per_match | 26.1 |
| on_target_share | 0.328 |
| xg_per_shot | 0.111 |
| goals_per_shot | 0.108 |
| outside_box_shot_share | 0.418 |
| passes_per_match | 1041.9 |
| pass_completion | 0.799 |
| corners_per_match | 9.460 |
| fouls_per_match | 20.8 |
| yellows_per_match | 4.090 |
| reds_per_match | 0.120 |
| penalties_per_match | 0.340 |
| penalty_conversion | 0.706 |
| offsides_per_match | 3.890 |
| set_piece_goal_share | 0.295 |
| late_goal_share | 0.209 |
| added_time_1h | 4.200 |
| added_time_2h | 9.180 |
| max_team_possession | 0.599 |
| min_team_possession | 0.405 |
