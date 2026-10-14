# Realism report

**27 of 27** league-level checks inside real-football ranges (top division, 2025-26, full season).

Ranges are approximate figures for a modern top-flight league and are deliberately wide.

| Check | Synthetic | Real-world range | |
|---|---|---|---|
| Goals per match | 2.908 | 2.5 - 3.2 | pass |
| Home win rate | 0.455 | 0.4 - 0.49 | pass |
| Draw rate | 0.258 | 0.2 - 0.3 | pass |
| Away win rate | 0.287 | 0.26 - 0.36 | pass |
| Shots per match | 26.2 | 22.0 - 28.5 | pass |
| Share of shots on target | 0.349 | 0.3 - 0.38 | pass |
| xG per shot | 0.110 | 0.09 - 0.13 | pass |
| Goals per shot | 0.107 | 0.09 - 0.13 | pass |
| Share of shots from outside the box | 0.348 | 0.28 - 0.45 | pass |
| Passes per match | 1025.5 | 850.0 - 1100.0 | pass |
| Pass completion | 0.799 | 0.78 - 0.86 | pass |
| Corners per match | 9.339 | 8.5 - 11.5 | pass |
| Fouls per match | 20.5 | 17.0 - 24.0 | pass |
| Yellow cards per match | 4.061 | 3.0 - 4.8 | pass |
| Red cards per match | 0.092 | 0.04 - 0.22 | pass |
| Penalties per match | 0.295 | 0.18 - 0.36 | pass |
| Penalty conversion | 0.804 | 0.68 - 0.86 | pass |
| Offsides per match | 4.184 | 2.5 - 5.0 | pass |
| Share of goals from set pieces (incl. penalties) | 0.330 | 0.2 - 0.34 | pass |
| Share of goals scored after the 75th minute | 0.226 | 0.17 - 0.3 | pass |
| Added time, first half (min) | 3.726 | 1.5 - 6.0 | pass |
| Added time, second half (min) | 8.868 | 4.0 - 10.0 | pass |
| Champion's points (38 games) | 79.0 | 78.0 - 100.0 | pass |
| 17th place points | 30.0 | 30.0 - 42.0 | pass |
| Bottom club's points | 26.0 | 10.0 - 35.0 | pass |
| Highest season possession share | 0.579 | 0.55 - 0.67 | pass |
| Lowest season possession share | 0.422 | 0.33 - 0.45 | pass |

## Do the hidden truths show up in the data?

For every planted trait we measure the matching statistic and compare it with peers (same position for players, same division for teams). *Detectable* means at least one standard deviation away from peers in the expected direction, on a usable sample.

- Previous season (2025-26, full season): **76/99** planted traits detectable
- Current season (2026-27, rounds played so far): **33/62** - smaller sample, so the Scout should also use last season's data.

### 2025-26

| Club | Player | Trait | Metric | Value | Peer mean | z | Detectable |
|---|---|---|---|---|---|---|---|
| Lowmarsh Harriers |  | set_piece_attack_strong | sp_xg_per_match | 0.409 | 0.288 | 1.820 | yes |
| Lowmarsh Harriers | Adam Vesodrez | clinical_finisher | goals_minus_xg_per_shot | 0.081 | 0.013 | 1.280 | yes |
| Lowmarsh Harriers | Malik Olotez | loses_ball_under_pressure | disp_per_press | 0.178 | 0.063 | 6.500 | yes |
| Dunvarrow Borough |  | set_piece_attack_strong | sp_xg_per_match | 0.441 | 0.288 | 2.240 | yes |
| Dunvarrow Borough |  | left_flank_focus | left_entry_share | 0.547 | 0.356 | 1.790 | yes |
| Dunvarrow Borough | Emil Varailo | loses_ball_under_pressure | disp_per_press | 0.245 | 0.094 | 4.840 | yes |
| Wyncaster County |  | set_piece_attack_strong | sp_xg_per_match | 0.371 | 0.288 | 1.330 | yes |
| Wyncaster County |  | left_flank_focus | left_entry_share | 0.561 | 0.356 | 1.890 | yes |
| Wyncaster County | Emil Darham | press_resistant_playmaker | disp_per_press | 0.035 | 0.063 | -1.320 | yes |
| Wyncaster County | Nils Salevuba | clinical_finisher | goals_minus_xg_per_shot | -0.017 | -0.024 | 0.290 | no |
| Highcrest Rangers |  | late_fade | late_xga_ratio | 1.692 | 1.547 | 0.470 | no |
| Highcrest Rangers | Leo Marimere | weak_in_the_air | aerial_win_rate | 0.253 | 0.540 | -4.110 | yes |
| Gallowmere Albion |  | fortress_home | home_minus_away_xgd | 0.744 | 0.365 | 1.400 | yes |
| Gallowmere Albion | Jordan Mareell | loses_ball_under_pressure | disp_per_press | 0.242 | 0.094 | 4.720 | yes |
| Gallowmere Albion | Elias Delarino | hothead | fouls_cards_per90 | 2.182 | 1.261 | 1.560 | yes |
| Stonemarsh Albion |  | left_flank_focus | left_entry_share | 0.533 | 0.356 | 1.670 | yes |
| Stonemarsh Albion |  | fortress_home | home_minus_away_xgd | 0.642 | 0.365 | 1.090 | yes |
| Stonemarsh Albion | Stellan Korino | goalkeeper_weak_on_crosses | claims_per90 | 0.383 | 2.424 | -2.290 | yes |
| Ravenholt City |  | set_piece_defense_weak | sp_xga_per_match | 0.405 | 0.288 | 1.720 | yes |
| Ravenholt City |  | left_flank_focus | left_entry_share | 0.534 | 0.356 | 1.680 | yes |
| Ravenholt City | Omar Halovik | goalkeeper_weak_on_crosses | claims_per90 | 0.505 | 2.424 | -2.180 | yes |
| Ravenholt City | Hugo Berodrez | loses_ball_under_pressure | disp_per_press | 0.243 | 0.074 | 8.200 | yes |
| Ironvale Rangers |  | set_piece_defense_weak | sp_xga_per_match | 0.342 | 0.288 | 0.860 | no |
| Ironvale Rangers | Nils Kelumenko | loses_ball_under_pressure | disp_per_press | 0.202 | 0.094 | 3.550 | yes |
| Corrowby Rangers |  | fortress_home | home_minus_away_xgd | 0.865 | 0.365 | 1.780 | yes |
| Corrowby Rangers | Elias Delerez | error_prone_passer | completion_over_expected | -0.192 | 0.023 | -4.580 | yes |
| Corrowby Rangers | Ben Jaruema | clinical_finisher | goals_minus_xg_per_shot | 0.007 | -0.030 | 0.670 | no |
| Duncliffe Albion |  | late_fade | late_xga_ratio | 1.720 | 1.547 | 0.590 | no |
| Duncliffe Albion |  | left_flank_focus | left_entry_share | 0.551 | 0.356 | 1.820 | yes |
| Duncliffe Albion | Emeka Morndo | clinical_finisher | goals_minus_xg_per_shot | 0.013 | 0.013 | 0.090 | no |
| Cragmouth County |  | poor_discipline | fouls_per_match | 17.5 | 10.3 | 5.590 | yes |
| Cragmouth County | Jonas Tamequist | weak_in_the_air | aerial_win_rate | 0.247 | 0.540 | -4.190 | yes |
| Calderwyn Town |  | late_fade | late_xga_ratio | 2.097 | 1.547 | 2.100 | yes |
| Calderwyn Town | Kofi Adoley | hothead | fouls_cards_per90 | 2.469 | 1.299 | 2.120 | yes |
| Quarlston Rangers |  | right_flank_focus | right_entry_share | 0.547 | 0.336 | 1.380 | yes |
| Quarlston Rangers | Milan Zelcott | goalkeeper_weak_on_crosses | claims_per90 | 0.360 | 2.424 | -2.310 | yes |
| Mistlecombe Town |  | fortress_home | home_minus_away_xgd | 0.142 | 0.365 | -0.460 | no |
| Mistlecombe Town | Mateo Dunevwick | elite_crosser | cross_completion | 0.487 | 0.330 | 1.440 | yes |
| Mistlecombe Town | David Yaribore | hothead | fouls_cards_per90 | 1.655 | 1.243 | 0.510 | no |
| Ashbrook Vale Rovers |  | right_flank_focus | right_entry_share | 0.562 | 0.336 | 1.480 | yes |
| Ashbrook Vale Rovers |  | fortress_home | home_minus_away_xgd | 0.877 | 0.365 | 1.820 | yes |
| Ashbrook Vale Rovers | Jakub Delanley | hothead | fouls_cards_per90 | 1.912 | 0.743 | 2.890 | yes |
| Ashbrook Vale Rovers | Sebastian Delanberg | error_prone_passer | completion_over_expected | -0.197 | 0.065 | -6.370 | yes |
| Varnholm FC |  | left_flank_focus | left_entry_share | 0.555 | 0.356 | 1.850 | yes |
| Varnholm FC | Leo Falaberg | weak_in_the_air | aerial_win_rate | 0.182 | 0.540 | -5.090 | yes |
| Varnholm FC | Zane Pelibnov | elite_crosser | cross_completion | 0.352 | 0.330 | 0.180 | no |
| Penmarrow Athletic |  | poor_discipline | fouls_per_match | 15.5 | 10.3 | 4.280 | yes |
| Penmarrow Athletic |  | fortress_home | home_minus_away_xgd | 0.687 | 0.365 | 1.230 | yes |
| Penmarrow Athletic | Santiago Sevanford | loses_ball_under_pressure | disp_per_press | 0.181 | 0.094 | 2.930 | yes |
| Penmarrow Athletic | Ali Yararzak | weak_in_the_air | aerial_win_rate | 0.235 | 0.540 | -4.360 | yes |
| Hollowmere Rovers |  | set_piece_attack_strong | sp_xg_per_match | 0.301 | 0.288 | 0.420 | no |
| Hollowmere Rovers | Dev Fenola | elite_crosser | cross_completion | 0.505 | 0.287 | 2.200 | yes |
| Hollowmere Rovers | Jonas Calennov | error_prone_passer | completion_over_expected | -0.170 | 0.023 | -4.160 | yes |
| Elderbridge City |  | right_flank_focus | right_entry_share | 0.572 | 0.336 | 1.550 | yes |
| Elderbridge City |  | fortress_home | home_minus_away_xgd | 0.430 | 0.365 | 0.430 | no |
| Elderbridge City | Hamza Ulibell | press_resistant_playmaker | disp_per_press | 0.028 | 0.063 | -1.700 | yes |
| Elderbridge City | Aurelio Darilard | goalkeeper_weak_on_crosses | claims_per90 | 0.457 | 2.424 | -2.220 | yes |
| Oxmere County |  | set_piece_attack_strong | sp_xg_per_match | 0.291 | 0.288 | 0.300 | no |
| Oxmere County |  | high_line_exposed | opp_offsides_per_match | 2.737 | 2.092 | 1.090 | yes |
| Oxmere County | Jonas Admere | weak_in_the_air | aerial_win_rate | 0.200 | 0.540 | -4.840 | yes |
| Grimsforth City | Sven Wilson | error_prone_passer | completion_over_expected | -0.177 | 0.020 | -4.970 | yes |
| Fennholt FC |  | right_flank_focus | right_entry_share | 0.573 | 0.346 | 3.860 | yes |
| Fennholt FC | Joel Moriric | elite_crosser | cross_completion | 0.500 | 0.260 | 2.160 | no |
| Breckhaven City | Ivan Ikodmere | weak_in_the_air | aerial_win_rate | 0.452 | 0.561 | -1.250 | yes |
| Kestrelford Athletic | Daniel Adorema | elite_crosser | cross_completion | 0.633 | 0.327 | 2.780 | yes |
| Wrenfield Harriers | Andre Fenumgard | loses_ball_under_pressure | disp_per_press | 0.199 | 0.072 | 5.930 | yes |
| Harrowdeen Athletic |  | set_piece_defense_weak | sp_xga_per_match | 0.303 | 0.235 | 1.620 | yes |
| Harrowdeen Athletic | Santiago Mareveke | error_prone_passer | completion_over_expected | -0.223 | -0.078 | -2.570 | yes |
| Pellmoor Borough |  | fortress_home | home_minus_away_xgd | 0.020 | 0.096 | -0.370 | no |
| Pellmoor Borough | Callum Naligard | error_prone_passer | completion_over_expected | -0.190 | -0.078 | -2.000 | yes |
| Vexley Cross Harriers |  | left_flank_focus | left_entry_share | 0.544 | 0.344 | 3.710 | yes |
| Vexley Cross Harriers | Diego Belani | loses_ball_under_pressure | disp_per_press | 0.184 | 0.078 | 4.650 | yes |
| Saltmere Athletic |  | set_piece_defense_weak | sp_xga_per_match | 0.383 | 0.235 | 3.270 | yes |
| Saltmere Athletic | Caleb Ikcott | goalkeeper_weak_on_crosses | claims_per90 | 0.416 | 1.946 | -1.920 | yes |
| Marrowgate Borough |  | late_fade | late_xga_ratio | 1.708 | 1.608 | 0.250 | no |
| Marrowgate Borough | Gabriel Delumard | weak_in_the_air | aerial_win_rate | 0.374 | 0.561 | -2.170 | yes |
| Morrowdene Wanderers |  | high_line_exposed | opp_offsides_per_match | 2.652 | 2.236 | 1.460 | yes |
| Morrowdene Wanderers | Eric Branemere | clinical_finisher | goals_minus_xg_per_shot | 0.047 | 0.015 | 0.690 | no |
| Kelvarth County |  | set_piece_defense_weak | sp_xga_per_match | 0.243 | 0.235 | 0.390 | no |
| Kelvarth County | Nathan Tamric | press_resistant_playmaker | disp_per_press | 0.018 | 0.077 | -2.420 | yes |
| Larkspur Bay County |  | left_flank_focus | left_entry_share | 0.561 | 0.344 | 3.990 | yes |
| Larkspur Bay County | Arlo Lorilici | press_resistant_playmaker | disp_per_press | 0.034 | 0.072 | -1.610 | yes |
| Coldwyke FC |  | late_fade | late_xga_ratio | 2.340 | 1.608 | 2.020 | yes |
| Coldwyke FC | Ethan Delarley | loses_ball_under_pressure | disp_per_press | 0.114 | 0.090 | 0.910 | no |
| Rookhaven Borough |  | fortress_home | home_minus_away_xgd | 0.129 | 0.096 | 0.560 | no |
| Rookhaven Borough | Marco Ishienko | weak_in_the_air | aerial_win_rate | 0.459 | 0.561 | -1.160 | yes |
| Sedgecombe Athletic | Adam Pelarwell | error_prone_passer | completion_over_expected | -0.180 | 0.020 | -5.040 | yes |
| Swanmoor Albion |  | set_piece_defense_weak | sp_xga_per_match | 0.299 | 0.235 | 1.540 | yes |
| Swanmoor Albion | Lucas Olodyi | loses_ball_under_pressure | disp_per_press | 0.183 | 0.090 | 2.920 | yes |
| Ambershaw United | Hamza Gilibrez | loses_ball_under_pressure | disp_per_press | 0.107 | 0.090 | 0.700 | no |
| Torvale United | Javier Calby | goalkeeper_weak_on_crosses | claims_per90 | 0.397 | 1.946 | -1.950 | yes |
| Fairhollow Athletic | Theo Ikodndo | weak_in_the_air | aerial_win_rate | 0.451 | 0.561 | -1.260 | yes |
| Thistlewick United |  | left_flank_focus | left_entry_share | 0.580 | 0.344 | 4.320 | yes |
| Thistlewick United | Milan Ulenzak | clinical_finisher | goals_minus_xg_per_shot | 0.079 | -0.013 | 3.950 | yes |
| Glimmerstone Borough |  | right_flank_focus | right_entry_share | 0.575 | 0.346 | 3.890 | yes |
| Glimmerstone Borough | Declan Ishieke | elite_crosser | cross_completion | 0.381 | 0.261 | 0.830 | no |
| Briarstead Rovers |  | late_fade | late_xga_ratio | 1.385 | 1.608 | -0.660 | no |
| Briarstead Rovers | Musa Sevorson | clinical_finisher | goals_minus_xg_per_shot | -0.125 | -0.002 | -4.760 | no |
| Blackmire Athletic | Tomas Halney | elite_crosser | cross_completion | 0.471 | 0.261 | 1.580 | yes |

### 2026-27 (so far)

| Club | Player | Trait | Metric | Value | Peer mean / before | z / change | Detectable |
|---|---|---|---|---|---|---|---|
| Lowmarsh Harriers |  | set_piece_attack_strong | sp_xg_per_match | 0.362 | 0.320 | 0.560 | no |
| Lowmarsh Harriers | Adam Vesodrez | clinical_finisher | goals_minus_xg_per_shot | 0.128 | 0.031 | 1.220 | yes |
| Lowmarsh Harriers | Malik Olotez | loses_ball_under_pressure | disp_per_press | 0.148 | 0.063 | 3.500 | yes |
| Dunvarrow Borough |  | set_piece_attack_strong | sp_xg_per_match | 0.565 | 0.320 | 2.560 | yes |
| Dunvarrow Borough |  | left_flank_focus | left_entry_share | 0.550 | 0.355 | 1.060 | yes |
| Dunvarrow Borough | Emil Varailo | loses_ball_under_pressure | disp_per_press | 0.163 | 0.081 | 2.080 | yes |
| Wyncaster County |  | set_piece_attack_strong | sp_xg_per_match | 0.415 | 0.320 | 1.080 | yes |
| Wyncaster County |  | left_flank_focus | left_entry_share | 0.529 | 0.355 | 0.960 | no |
| Wyncaster County | Emil Darham | press_resistant_playmaker | disp_per_press | 0.031 | 0.063 | -0.670 | no |
| Wyncaster County | Nils Salevuba | clinical_finisher | goals_minus_xg_per_shot | 0.030 | 0.023 | - | no |
| Gallowmere Albion |  | fortress_home | home_minus_away_xgd | - | -0.279 | - | no |
| Gallowmere Albion | Jordan Mareell | loses_ball_under_pressure | disp_per_press | 0.262 | 0.081 | 4.360 | yes |
| Gallowmere Albion | Elias Delarino | hothead | fouls_cards_per90 | 2.486 | 1.323 | 2.790 | yes |
| Stonemarsh Albion |  | left_flank_focus | left_entry_share | 0.551 | 0.355 | 1.070 | yes |
| Stonemarsh Albion |  | fortress_home | home_minus_away_xgd | - | -0.279 | - | no |
| Stonemarsh Albion | Stellan Korino | goalkeeper_weak_on_crosses | claims_per90 | 0.455 | 2.516 | -2.080 | yes |
| Ravenholt City |  | set_piece_defense_weak | sp_xga_per_match | 0.606 | 0.320 | 3.940 | yes |
| Ravenholt City |  | left_flank_focus | left_entry_share | 0.487 | 0.355 | 0.730 | no |
| Ravenholt City | Omar Halovik | goalkeeper_weak_on_crosses | claims_per90 | 0.363 | 2.516 | -2.180 | yes |
| Ravenholt City | Hugo Berodrez | loses_ball_under_pressure | disp_per_press | 0.196 | 0.069 | 3.630 | yes |
| Ironvale Rangers |  | set_piece_defense_weak | sp_xga_per_match | 0.247 | 0.320 | -0.850 | no |
| Ironvale Rangers | Nils Kelumenko | loses_ball_under_pressure | disp_per_press | 0.162 | 0.081 | 2.050 | no |
| Corrowby Rangers |  | fortress_home | home_minus_away_xgd | -0.627 | -0.279 | -0.410 | no |
| Corrowby Rangers | Elias Delerez | error_prone_passer | completion_over_expected | -0.185 | 0.031 | -6.420 | yes |
| Corrowby Rangers | Ben Jaruema | clinical_finisher | goals_minus_xg_per_shot | 0.082 | -0.012 | - | no |
| Duncliffe Albion |  | late_fade | late_xga_ratio | 1.329 | 1.572 | -0.480 | no |
| Duncliffe Albion |  | left_flank_focus | left_entry_share | 0.560 | 0.355 | 1.120 | yes |
| Duncliffe Albion | Emeka Morndo | clinical_finisher | goals_minus_xg_per_shot | 0.175 | 0.031 | 1.790 | no |
| Calderwyn Town |  | late_fade | late_xga_ratio | 1.595 | 1.572 | 0.070 | no |
| Calderwyn Town | Kofi Adoley | hothead | fouls_cards_per90 | 2.209 | 1.304 | 2.460 | yes |
| Quarlston Rangers |  | right_flank_focus | right_entry_share | 0.589 | 0.342 | 1.320 | yes |
| Quarlston Rangers | Milan Zelcott | goalkeeper_weak_on_crosses | claims_per90 | - | - | - | no |
| Mistlecombe Town |  | fortress_home | home_minus_away_xgd | - | -0.279 | - | no |
| Ravenholt City | Mateo Dunevwick | elite_crosser | cross_completion | 0.316 | 0.298 | 0.000 | no |
| Mistlecombe Town | David Yaribore | hothead | fouls_cards_per90 | 2.638 | 1.357 | 1.970 | yes |
| Varnholm FC |  | left_flank_focus | left_entry_share | 0.510 | 0.355 | 0.860 | no |
| Varnholm FC | Leo Falaberg | weak_in_the_air | aerial_win_rate | 0.170 | 0.568 | -5.770 | yes |
| Varnholm FC | Zane Pelibnov | elite_crosser | cross_completion | 0.467 | 0.298 | 0.810 | no |
| Penmarrow Athletic |  | poor_discipline | fouls_per_match | 14.2 | 9.635 | 2.870 | yes |
| Penmarrow Athletic |  | fortress_home | home_minus_away_xgd | - | -0.279 | - | no |
| Penmarrow Athletic | Santiago Sevanford | loses_ball_under_pressure | disp_per_press | 0.105 | 0.081 | 0.730 | no |
| Penmarrow Athletic | Ali Yararzak | weak_in_the_air | aerial_win_rate | 0.250 | 0.568 | -4.660 | yes |
| Hollowmere Rovers |  | set_piece_attack_strong | sp_xg_per_match | 0.367 | 0.320 | 0.620 | no |
| Hollowmere Rovers | Dev Fenola | elite_crosser | cross_completion | 0.529 | 0.343 | 1.410 | yes |
| Ironvale Rangers | Jonas Calennov | error_prone_passer | completion_over_expected | -0.172 | 0.031 | -6.070 | no |
| Elderbridge City |  | right_flank_focus | right_entry_share | 0.574 | 0.342 | 1.240 | yes |
| Elderbridge City |  | fortress_home | home_minus_away_xgd | 0.403 | -0.279 | 0.820 | no |
| Elderbridge City | Hamza Ulibell | press_resistant_playmaker | disp_per_press | 0.017 | 0.063 | -1.170 | yes |
| Elderbridge City | Aurelio Darilard | goalkeeper_weak_on_crosses | claims_per90 | 0.091 | 2.516 | -2.460 | yes |
| Oxmere County |  | set_piece_attack_strong | sp_xg_per_match | 0.550 | 0.320 | 2.410 | yes |
| Oxmere County |  | high_line_exposed | opp_offsides_per_match | 2.700 | 2.115 | 2.360 | yes |
| Oxmere County | Jonas Admere | weak_in_the_air | aerial_win_rate | 0.455 | 0.568 | -1.830 | yes |
| Fennholt FC |  | right_flank_focus | right_entry_share | 0.615 | 0.342 | 1.450 | yes |
| Fennholt FC | Joel Moriric | elite_crosser | cross_completion | 0.000 | - | - | no |
| Duncliffe Albion | Daniel Adorema | elite_crosser | cross_completion | - | - | - | no |
| Pellmoor Borough |  | fortress_home | home_minus_away_xgd | - | -0.279 | - | no |
| Pellmoor Borough | Callum Naligard | error_prone_passer | completion_over_expected | - | - | - | no |
| Marrowgate Borough |  | late_fade | late_xga_ratio | 1.625 | 1.572 | 0.130 | no |
| Marrowgate Borough | Gabriel Delumard | weak_in_the_air | aerial_win_rate | 0.184 | 0.568 | -5.580 | yes |
| Mistlecombe Town |  | style_change_press_intensity | pressures_per_opp_pass | 0.334 | 0.267 | 0.067 | yes |
| Calderwyn Town |  | style_change_press_intensity | pressures_per_opp_pass | 0.235 | 0.320 | -0.085 | yes |
| Calderwyn Town |  | style_change_directness | long_pass_share | 0.146 | 0.076 | 0.070 | yes |
| Dunvarrow Borough | Ethan Nalidra | clinical_finisher (natural) | goals_minus_xg_per_shot | 0.127 | 0.031 | 1.200 | yes |
| Calderwyn Town | Sven Lanilici | press_resistant_playmaker (natural) | disp_per_press | 0.030 | 0.063 | -0.700 | no |
| Elderbridge City | Bruno Vesodero | hothead (natural) | fouls_cards_per90 | 1.187 | 0.671 | 1.240 | yes |

## League summaries

### Top division 2025-26

| Metric | Value |
|---|---|
| goals_per_match | 2.908 |
| home_win_rate | 0.455 |
| draw_rate | 0.258 |
| away_win_rate | 0.287 |
| shots_per_match | 26.2 |
| on_target_share | 0.349 |
| xg_per_shot | 0.110 |
| goals_per_shot | 0.107 |
| outside_box_shot_share | 0.348 |
| passes_per_match | 1025.5 |
| pass_completion | 0.799 |
| corners_per_match | 9.339 |
| fouls_per_match | 20.5 |
| yellows_per_match | 4.061 |
| reds_per_match | 0.092 |
| penalties_per_match | 0.295 |
| penalty_conversion | 0.804 |
| offsides_per_match | 4.184 |
| set_piece_goal_share | 0.330 |
| late_goal_share | 0.226 |
| added_time_1h | 3.726 |
| added_time_2h | 8.868 |
| max_team_possession | 0.579 |
| min_team_possession | 0.422 |
| champion_points | 79.0 |
| safety_points | 30.0 |
| bottom_points | 26.0 |

### Second tier 2025-26

| Metric | Value |
|---|---|
| goals_per_match | 2.179 |
| home_win_rate | 0.324 |
| draw_rate | 0.384 |
| away_win_rate | 0.292 |
| shots_per_match | 20.8 |
| on_target_share | 0.338 |
| xg_per_shot | 0.105 |
| goals_per_shot | 0.100 |
| outside_box_shot_share | 0.396 |
| passes_per_match | 1031.7 |
| pass_completion | 0.761 |
| corners_per_match | 9.125 |
| fouls_per_match | 20.1 |
| yellows_per_match | 4.118 |
| reds_per_match | 0.063 |
| penalties_per_match | 0.246 |
| penalty_conversion | 0.816 |
| offsides_per_match | 4.473 |
| set_piece_goal_share | 0.333 |
| late_goal_share | 0.245 |
| added_time_1h | 3.486 |
| added_time_2h | 8.716 |
| max_team_possession | 0.582 |
| min_team_possession | 0.416 |

### Top division (rounds so far) 2026-27

| Metric | Value |
|---|---|
| goals_per_match | 3.210 |
| home_win_rate | 0.350 |
| draw_rate | 0.250 |
| away_win_rate | 0.400 |
| shots_per_match | 26.0 |
| on_target_share | 0.348 |
| xg_per_shot | 0.113 |
| goals_per_shot | 0.119 |
| outside_box_shot_share | 0.330 |
| passes_per_match | 1033.6 |
| pass_completion | 0.798 |
| corners_per_match | 9.430 |
| fouls_per_match | 19.3 |
| yellows_per_match | 3.780 |
| reds_per_match | 0.110 |
| penalties_per_match | 0.230 |
| penalty_conversion | 0.609 |
| offsides_per_match | 4.230 |
| set_piece_goal_share | 0.277 |
| late_goal_share | 0.268 |
| added_time_1h | 3.710 |
| added_time_2h | 9.040 |
| max_team_possession | 0.600 |
| min_team_possession | 0.422 |
