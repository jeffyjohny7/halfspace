# Halfspace — design notes

Subject: a live match companion for football fans. Primary job: watch the match with
AI insights that are checked before they appear, and see the pre-match scouting tested live.
Audience: casual and data-minded fans, in English, Malayalam and Hindi.

## Tokens
Colour (night pitch + chalk; team kits carry identity, chalk carries the AI's voice)
- turf-0  #0C1814  page
- turf-1  #11211B  panels / pitch base
- turf-2  #183028  raised, pitch stripe
- line    #26443A  hairlines, pitch markings at rest
- chalk   #ECEAE0  text, AI annotations
- chalk-2 #A7BAAF  secondary text
- chalk-3 #6C857A  tertiary, disabled
Team colours come from the clubs' kits (dark kits fall back to their second colour).
Rating bands (match ratings only, never decoration): poor <6 #E0644F, ok 6-6.9 #E3B341,
good 7-7.9 #5FC27E, great 8+ #4FB3D9, dark text on the chip.

Type: Anek (Latin, Malayalam, Devanagari share one design) with Noto Kufi Arabic for Arabic,
merged into the same family by unicode-range (same weight and width descriptors, or Chrome
won't merge them). Condensed width (75) at 700 for the scoreboard, names and big numbers;
normal width at 400/500 for reading. Arabic text gets dir="rtl" and looser line height.

Language and style: a language menu (five languages) plus Casual / Analyst buttons when the
chosen language has more than one style. Every text element carries its real language, so a
safe template's translated headline over an English fact line is tagged correctly.

## Layout
Match: scoreboard on top; the pitch is the stage (left, wide); the scout's calls and the
match numbers sit in a quiet rail (right); the timeline and the viewer switch run along
the bottom. On phones: score, pitch, graphic, then controls fixed at the bottom.

## Principles
1. The pitch is the stage. Graphics arrive on the touchline edge of the pitch and the moment
   they describe is ringed in chalk. That arrival is the one orchestrated motion.
2. Calm density: a handful of numbers at a time, details on tap.
3. Trust shown, not told: every graphic carries a checked mark; tapping it shows the facts
   it was written from and how many drafts were rejected.
4. No all-caps labels, no monospace data labels, no identical card grids.

## Player card
A chalk-paper sheet over the night pitch (same idea as the graphics: chalk annotations on the
pitch). Dark ink on #EFEDE4, a 1.5 px ink rule under the title and above each section, hairline
rows for the numbers, condensed bold values right-aligned. Portrait on the team colour with the
shirt number. Heat map: pale yellow to red on a light pitch, always attacking right. Opens as a
modal dialog (focus moves to the close button; Escape, the cross or a click outside closes it),
full screen on phones.

## Match centre
Tabs above the stage, like a broadcaster's match centre: Live, Line-ups, Stats, Commentary. The
rail and the replay controls stay put, so switching tabs never loses the match.

## League hub (hub.css)
The match centre now lives inside a league hub: Home, Matches, Table, Stats, Clubs, Players, Ask.
Structure follows a top league's site (fixture lists with win chances, a table with zones and form,
stats cards that feature the leader, crest wall, club and player pages); the look is our own.
- Club kits carry the colour: fixture cards fade from the home kit to the away kit, club and player
  headers are washed in the kit, leader cards in the leader's kit. When two kits clash, the away
  club falls back to its other colour (or chalk).
- crown gold #E9B949 marks the league's best: leaders' numbers, champions, the season menu.
- live red #FF5A46 only for what is live: the broadcast match's badge, card glow, Watch live.
- Zones reuse the rating colours: Continental Cup blue, Shield green, play-offs amber, relegation red.
- Images (Higgsfield): night stadium (home), tunnel (matches), trophy (table), stadium (clubs).
- One orchestrated motion: the home hero settles and the two crests rise. The live dot pulses.
  Both respect reduced motion.
- Casual / Analyst applies everywhere. Analyst adds xG columns and the charts: points race,
  results against chances, goals against xG, percentile bars, when the goals come.
- Live ratings live only in the match centre (Ratings tab, at the replay clock); the Players tab is
  the season. Substitutes appear in Ratings only once they have come on.

## My Halfspace and alerts
- The fan's initial in the top bar opens My Halfspace; the bell appears only once alerts can arrive
  (a club or player followed, alerts on). Unread count in live red, because alerts are about now.
- My Halfspace is a settings page that shows its working: "What Halfspace remembers" lists every fact
  with where it came from ("You set this here" or the fan's own words from Ask) and a Delete button.
  "Forget everything" asks for a second click.
- Toasts drop in at the top right, coloured by what the news means for the fan (green good, red bad,
  gold neutral), and fade after nine seconds. At most three on screen; when a jump in the replay
  releases several at once, only the latest shows, with "N earlier alerts in the bell". Opening the
  tray clears the toasts.
- Home shows one "for you" strip (your club's fixture, alerts on); nothing else changes, so a fan
  without a profile sees the same app.
