# Do the agents stick to the facts?

Generated 2026-10-23 17:27. Judge: Foundry GroundednessEvaluator on `gpt-5-mini` (1-5, pass at 3+). Text in other languages is translated back to English before it is judged.

Run in the Foundry portal: https://ai.azure.com/resource/build/evaluation/73a2add7-dabe-4cdd-88b6-7a4cf6e70bd5?wsid=/subscriptions/80923ec5-8c57-431a-856f-327b3bfc4e73/resourceGroups/rg-insidethegame/providers/Microsoft.CognitiveServices/accounts/itg-foundry-jeffy1410/projects/insidethegame&tid=60a984ad-649b-4f6f-9f87-f3be59d2b7b0

| | Items | Grounded (avg, 1-5) | Grounded (pass) | Numbers traced | Right language |
|---|---:|---:|---:|---:|---:|
| **All** | 133 | 4.61 | 95% | 96% | 100% |
| Full-time recap · English | 1 | 5.00 | 100% | 100% | 100% |
| Graphics · Arabic | 22 | 4.77 | 100% | 95% | 100% |
| Graphics · English | 44 | 4.75 | 100% | 95% | 100% |
| Graphics · Hindi | 22 | 4.27 | 86% | 95% | 100% |
| Graphics · Malayalam | 22 | 4.41 | 86% | 95% | 100% |
| Graphics · Spanish | 22 | 4.68 | 96% | 100% | 100% |

## The broadcast run

- 22 graphics, 132 versions (viewer × language): 132 written by the model, 0 by the safe template.
- The Verifier sent 1 graphics back for a rewrite; 0 ended on the safe template.

## Lowest scores

What the judge flagged, so the prompts can improve:

- **cue-002 casual/hi** (2/5): Lowmarsh Harriers के कॉर्नर खतरनाक / Lowmarsh Harriers के कॉर्नर और चौड़ी फ्री किक 0.45 गोल प्रति मैच हैं। बॉक्स में डिलीवरी पर जाएँगे, Jonas Admere हवा में सिर्फ 27% जीतते हैं।  
  _In English:_ Lowmarsh Harriers' corners dangerous / Lowmarsh Harriers' corners and wide free kicks are 0.45 goals per match. On deliveries into the box, Jonas Admere wins only 27% in the air.  
  _Judge:_ Let's think step by step: The response directly references the two main facts from the context — Lowmarsh's set-piece value (0.45) and Jonas Admere's 27% aerial duels won — so it is relevant. However, it inaccurately phrases 0.45 xG as "0.45 goals per match" (conflating xG with actual goals), and it omits context details like the league median xG (0.25), the CB median (57%), and the explicit expec
- **cue-002 casual/ml** (2/5): Lowmarsh Harriers കോർണർ ഭീഷണി / Lowmarsh Harriersന്റെ കോർണറുകൾ ഓരോ മാച്ചിലും 0.45 ഗോൾ. Jonas Admere വായുവിലെ പോരാട്ടങ്ങളിൽ 27% മാത്രം ജയിക്കുന്നു, അതിനാൽ ബോക്സിലേക്കുള്ള ഡെലിവറികൾക്ക് ശ്രദ്ധിക്കുക.  
  _In English:_ Lowmarsh Harriers corner threat / Lowmarsh Harriers' corners 0.45 goals per match. Jonas Admere wins only 27% of aerial duels, so watch the deliveries into the box.  
  _Judge:_ Let's think step by step: The response correctly captures the key points from the context: Lowmarsh create 0.45 xG from set pieces and Jonas Admere wins only 27% of aerial duels, and it correctly infers that deliveries into the box should be targeted. However, it misstates 0.45 xG as "0.45 goals per match," which is an inaccurate representation of the metric, and it omits mention of wide free kick
- **cue-008 casual/ml** (2/5): കലാപം 72, മിനിറ്റിന് 2.8 / കഴിഞ്ഞ 10 മിനിറ്റില്‍ കലാപം 72, മിനിറ്റിന് 2.8. Oxmere Countyയുടെ ഹൈലൈൻ (2.10 ഓഫ്‌സൈഡ്/മത്സ്യം നല്‍കുന്നത്) ഒപ്പം Adam Vesodrezയുടെ (0.48 എക്സ് ജി) ക്ലിയർ ചാൻസ് പിന്നിലേക്ക് പന്തുകൾ ഭീഷണിയാക്കുന്നു.  
  _In English:_ Kalapam 72, 2.8 per minute / In the last 10 minutes Kalapam 72, 2.8 per minute. Oxmere County's high line (2.10 offside/awarded) and Adam Vesodrez's (0.48 xG) clear chance are threatening balls behind.  
  _Judge:_ Let's think step by step: The response clearly attempts to mirror the context — it includes the 72 value and the 2.8 changes per minute, and it references Oxmere's high line and Adam Vesodrez's 0.48 xG clear chance, which are all present in the context. However, it introduces an incorrect or unclear term "Kalapam 72" instead of the context's "chaos index 72," and slightly alters phrasing around of
- **cue-010 casual/es** (2/5): Confirmado: Jonas Admere falla duelos aéreos / Min 35: Jonas Admere 25% de duelos aéreos (4). Confirma la alerta: Lowmarsh Harriers generan 0.45 goles por partido con córner y tiros libres laterales.  
  _In English:_ Confirmed: Jonas Admere fails aerial duels / Min 35: Jonas Admere 25% of aerial duels (4). Confirms the alert: Lowmarsh Harriers generate 0.45 goals per match with corner and wide free kicks.  
  _Judge:_ Let's think step by step: The RESPONSE correctly notes Jonas Admere has 25% from 4 aerial duels at minute 35, which meets the context's confirmation rule (40% or fewer from at least 4 duels) so confirming the aerial-duel concern is supported. However, the RESPONSE incorrectly states that Lowmarsh Harriers "generate 0.45 goals per match" from corners and wide free kicks — the CONTEXT specifies 0.45
- **cue-010 casual/hi** (2/5): प्रेडिक्शन कन्फर्म: Jonas Admere 25% / 35वें मिनट में Jonas Admere ने 4 दुयलों में 25% जीते। Lowmarsh Harriers के कॉर्नर 0.45 गोल प्रति मैच हैं, चिंता वाजिब।  
  _In English:_ Prediction Confirm: Jonas Admere 25% / In the 35th minute Jonas Admere won 25% in 4 duels. Lowmarsh Harriers' corners are 0.45 goals per match, concern justified.  
  _Judge:_ Let's think step by step: The response correctly notes that at minute 35 Jonas Admere has won 25% from 4 aerial duels, and correctly concludes the scout's concern about set pieces is justified given Lowmarsh's 0.45 figure. However, it slightly misstates the context by calling Lowmarsh's 0.45 value 'goals per match' rather than the context's 'xG per match' (expected goals). The response also omits 

## Code checks that failed

- **cue-005 analyst/en**: numbers not in the context: 3
- **cue-005 casual/ar**: numbers not in the context: 3
- **cue-005 casual/en**: numbers not in the context: 3
- **cue-005 casual/hi**: numbers not in the context: 3
- **cue-005 casual/ml**: numbers not in the context: 3
