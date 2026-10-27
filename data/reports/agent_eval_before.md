# Do the agents stick to the facts?

Generated 2026-10-23 16:18. Judge: Foundry GroundednessEvaluator on `gpt-5-mini` (1-5, pass at 3+). Text in other languages is translated back to English before it is judged.

Run in the Foundry portal: https://ai.azure.com/resource/build/evaluation/9746f5b4-2167-4226-9b19-a2d5b94ef8fd?wsid=/subscriptions/80923ec5-8c57-431a-856f-327b3bfc4e73/resourceGroups/rg-insidethegame/providers/Microsoft.CognitiveServices/accounts/itg-foundry-jeffy1410/projects/insidethegame&tid=60a984ad-649b-4f6f-9f87-f3be59d2b7b0

| | Items | Grounded (avg, 1-5) | Grounded (pass) | Numbers traced | Right language |
|---|---:|---:|---:|---:|---:|
| **All** | 132 | 4.58 | 93% | 100% | 100% |
| Full-time recap · English | 1 | 5.00 | 100% | 100% | 100% |
| Graphics · Arabic | 22 | 4.68 | 96% | 100% | 100% |
| Graphics · English | 43 | 4.58 | 93% | 100% | 100% |
| Graphics · Hindi | 22 | 4.55 | 91% | 100% | 100% |
| Graphics · Malayalam | 22 | 4.55 | 96% | 100% | 100% |
| Graphics · Spanish | 22 | 4.50 | 91% | 100% | 100% |

## The broadcast run

- 22 graphics, 132 versions (viewer × language): 131 written by the model, 1 by the safe template.
- The Verifier sent 3 graphics back for a rewrite; 1 ended on the safe template.

## Lowest scores

What the judge flagged, so the prompts can improve:

- **cue-001 analyst/en** (2/5): Scouting: Set Pieces vs Crosses / Lowmarsh Harriers sit 3, Oxmere County 9. xG, field tilt and PPDA reveal the key differences ahead of kick-off.  
  _Judge:_ Let's think step by step: The response correctly echoes the match subject and the table positions (Lowmarsh Harriers 3, Oxmere County 9) and highlights set pieces vs crosses, which matches the context. However, it introduces specific metrics — xG, field tilt and PPDA — as revealing key differences, but those metrics are not mentioned or supported by the provided context. Because the reply mixes ac
- **cue-005 casual/en** (2/5): Watch Oxmere's high line / They get caught offside 2.10 times per match (league median 1.70). Lowmarsh make only 0.01 on counters (12th percentile). Adam Vesodrez +0.17 goals/shot.  
  _Judge:_ Let's think step by step: The response closely mirrors the statistics from the context — it repeats the 2.10 offsides vs 1.70 median, the Lowmarsh Harriers' 0.01 xG on the counter (12th percentile), and Adam Vesodrez's +0.17 goals/shot — all of which are supported by the context. However, the response introduces a team name, "Oxmere," with the sentence "Watch Oxmere's high line," which is not pres
- **cue-005 casual/es** (2/5): Línea alta: cuidado con Adam Vesodrez / Rivales en fuera de juego 2.10 (mediana 1.70). Lowmarsh Harriers crean 0.01 a la contra (12th percentile). Adam Vesodrez 0.17 goles por tiro (ST median 0.02).  
  _In English:_ High line: careful with Adam Vesodrez / Opponents offside 2.10 (median 1.70). Lowmarsh Harriers create 0.01 on the counter (12th percentile). Adam Vesodrez 0.17 goals per shot (ST median 0.02).  
  _Judge:_ Let's think step by step: The response closely mirrors the context's key numbers (opponents offside 2.10 vs league median 1.70; Lowmarsh Harriers 0.01 xG on the counter at the 12th percentile) and draws a relevant tactical takeaway (play a high line: careful with Adam Vesodrez). However, it slightly misrepresents the Adam Vesodrez metric: the context states he "scores 0.17 more goals per shot than
- **cue-005 casual/hi** (2/5): ऊंची लाइन से Oxmere County सावधान / विरोधी 2.10 बार ऑफसाइड पकड़े जाते हैं, पीछे की गेंदें ख़तरा; Lowmarsh Harriers काउंटर 0.01 xG (12वां), Adam Vesodrez शॉट पर xG से 0.17 ज्यादा गोल।  
  _In English:_ Beware Oxmere County from the high line / Opponents are caught offside 2.10 times, through balls are a threat; Lowmarsh Harriers counter 0.01 xG (12th), Adam Vesodrez scores 0.17 more goals than xG per shot.  
  _Judge:_ Let's think step by step: The response largely mirrors the facts in the context — it repeats the offside figure (2.10), notes the risk of balls in behind/through balls, reports Lowmarsh Harriers' 0.01 xG on the counter (12th percentile), and restates Adam Vesodrez's +0.17 goals per shot vs xG. However, the response adds "Beware Oxmere County," a team name not present in the provided context, intro
- **cue-008 analyst/en** (2/5): Chaos index 72, patterns shifting / Chaos index 72; 2.8 changes/min. field tilt 80%; opponents offside 2.10. xG and PPDA profiles unchanged, but turnovers expose high-line risk.  
  _Judge:_ Let's think step by step: The response correctly restates key context facts — chaos index 72, 2.8 changes/min, and the 80% field tilt (matching Oxmere's 80% of final-third passes) and opponents offside 2.10 — and draws the same conclusion that turnovers expose a high-line risk. However, it adds the claim that "xG and PPDA profiles [are] unchanged," which is not supported or mentioned in the provid
