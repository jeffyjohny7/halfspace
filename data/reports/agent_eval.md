# Do the agents stick to the facts?

Generated 2026-10-27 20:23. Judge: Foundry GroundednessEvaluator on `gpt-4.1` (1-5, pass at 3+). Text in other languages is translated back to English before it is judged.

Run in the Foundry portal: https://ai.azure.com/resource/build/evaluation/b5c3916f-d492-40ac-8d57-5a33eeae5d96?wsid=/subscriptions/80923ec5-8c57-431a-856f-327b3bfc4e73/resourceGroups/rg-insidethegame/providers/Microsoft.CognitiveServices/accounts/itg-foundry-jeffy1410/projects/insidethegame&tid=60a984ad-649b-4f6f-9f87-f3be59d2b7b0

| | Items | Grounded (avg, 1-5) | Grounded (pass) | Numbers traced | Right language |
|---|---:|---:|---:|---:|---:|
| **All** | 198 | 4.62 | 96% | 100% | 100% |
| Ask answers · English | 3 | 2.67 | 33% | 100% | 100% |
| Ask answers · Malayalam | 1 | 5.00 | 100% | 100% | 100% |
| Full-time recap · English | 1 | 5.00 | 100% | 100% | 100% |
| Graphics · Arabic | 30 | 4.50 | 90% | 100% | 100% |
| Graphics · English | 76 | 4.63 | 99% | 100% | 100% |
| Graphics · Hindi | 29 | 4.59 | 97% | 100% | 100% |
| Graphics · Malayalam | 29 | 4.86 | 100% | 100% | 100% |
| Graphics · Spanish | 29 | 4.71 | 96% | 100% | 100% |

## The broadcast run

- 30 graphics, 198 versions (viewer × language): 193 written by the model, 5 by the safe template.
- The Verifier sent 3 graphics back for a rewrite; 1 ended on the safe template.

## Lowest scores

What the judge flagged, so the prompts can improve:

- **cue-008 casual/es** (2/5): Rohan Olarici se lesiona al minuto 7 / Entra Kofi Falilisson muy pronto. Puede romper la entrega desde las bandas y los córners dirigidos a Jonas Admere en el aire.  
  _In English:_ Rohan Olarici is injured at minute 7 / Kofi Falilisson enters very early. He can break the supply from the wings and the corners directed to Jonas Admere in the air.  
  _Judge:_ Let's think step by step: The response correctly states that Rohan Olarici is injured at minute 7 and that Kofi Falilisson comes on very early, which matches the context. However, the response says 'He can break the supply from the wings and the corners directed to Jonas Admere in the air.' This is a misinterpretation: the context says that bringing on Kofi Falilisson could disrupt Lowmarsh’s plan
- **cue-009 casual/ar** (2/5): فوضى 28 من 100 و2.1 تبدلات / ضغط Oxmere County و19% خسارة Malik Olotez عند الضغط في ملعب فوضوي (28 من 100، 2.1 تبدلات/دقيقة) قد تمنح Lowmarsh Harriers ركلات ركنية أو عرضيات.  
  _In English:_ Chaos 28 out of 100 and 2.1 substitutions / Oxmere County pressure and 19% Malik Olotez loss under pressure in a chaotic field (28 out of 100, 2.1 substitutions/minute) may grant Lowmarsh Harriers corners or crosses.  
  _Judge:_ Let's think step by step: The response attempts to restate the context but introduces a significant inaccuracy. The context says '2.1 changes of possession per minute,' but the response incorrectly refers to '2.1 substitutions/minute.' This is a factual error, as substitutions and changes of possession are not the same. The rest of the response does attempt to capture the idea that Oxmere's pressi
- **cue-020 casual/hi** (2/5): 56वां मिनट: 68 की उथल-पुथल / 68 की उथल-पुथल, हर मिनट 2.8 पोजेशन बदलते हैं. Lowmarsh Harriers के कॉर्नर/फ्री किक हर टर्नओवर पर Oxmere County के बॉक्स में खतरा है.  
  _In English:_ 56th minute: 68's upheaval / 68's upheaval, possession changes every 2.8 minutes. Lowmarsh Harriers' corners/free kicks create danger in Oxmere County's box on every turnover.  
  _Judge:_ Let's think step by step: The response references the 56th minute and the chaos index of 68, which matches the context. It also mentions possession changes, but incorrectly states 'possession changes every 2.8 minutes' instead of '2.8 changes of possession per minute' as in the context. The response correctly notes that Lowmarsh Harriers' set pieces (corners/free kicks) create danger in Oxmere Cou
- **cue-027 casual/ar** (2/5): Lowmarsh يضغط والوقت جنوني / مؤشر الفوضى 69 و2.9 تغييرات في الدقيقة في آخر 10 دقائق. Lowmarsh استحوذ 59% وصنع 70% من تمريرات الثلث الأخير ويهيئون ركلات ركنية وعرضيات لهدف قاتل.  
  _In English:_ Lowmarsh presses and the time is crazy. / Chaos index 69 and 2.9 substitutions per minute in the last 10 minutes. Lowmarsh possessed 59% and made 70% of final third passes and are preparing corners and crosses for a killer goal.  
  _Judge:_ Let's think step by step: The response attempts to summarize the context, mentioning Lowmarsh's pressing and the chaotic nature of the match, which aligns with the chaos index and possession changes. It correctly states Lowmarsh's 59% possession and 70% of final-third passes, and references their preparation for corners and crosses, which matches the context's mention of set-piece and wide deliver
- **cue-027 club:C20/en** (2/5): Hold on, Oxmere! / Chaos index 69 and 2.9 changes of possession per minute, Lowmarsh 59% possession and 70% final-third passes—under pressure but still in it.  
  _Judge:_ Let's think step by step: The response references the chaos index (69), changes of possession per minute (2.9), Lowmarsh's 59% possession, and 70% of final-third passes, all of which are directly from the context. However, the response frames the situation as 'under pressure but still in it,' and addresses Oxmere, which is not mentioned in the context. The context is focused on Lowmarsh Harriers' 
