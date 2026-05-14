# Babel's Glyph — Presentation Script

A spoken script you can read aloud during a live demo or recorded walkthrough of
**Babel's Glyph**. Total runtime: roughly **3 minutes** at a relaxed pace.

Stage directions and visual cues are in *italics* — say only the lines marked
**SAY**. Pauses are marked with `[beat]` (~0.5 s) and `[pause]` (~1 s).

---

## 0. Cold Open — before the trailer plays  (~10 s)

*Stand in front of the screen. Game title card or trailer paused on first frame.*

> **SAY:** Imagine the great library of Babel.  [beat]  Every machine ever
> dreamed of, every blueprint ever burned — all of it, written in glyphs.
> [pause]  And the past is collapsing behind you.

*Hit Play on the trailer (or start the game).*

---

## 1. The Hook — while the trailer plays  (~30 s)

*Trailer rolls. Speak over it, matching the energy on screen.*

> **SAY:** This is **Babel's Glyph** — an endless side-scrolling runner about
> outrunning history itself.  [beat]
> You play a glyph-thief sprinting through three ancient zones — sandstone
> outskirts, Da Vinci's forge, and a sky-workshop above the clouds — while the
> world literally falls apart behind you.  [pause]
> Every run is a remix. Every meter you survive… rewrites the past.

*Trailer ends, cut to title screen of the live game.*

---

## 2. The Pitch — what is it?  (~25 s)

*Title screen visible. Calm, confident voice.*

> **SAY:** Under the hood, Babel's Glyph is a hand-crafted 2-D platformer
> built from scratch in **Python and pygame**.  [beat]
> No game engine. No store-bought assets. Every tile, every parallax layer,
> every animation frame is generated in code at runtime.  [pause]
> The whole game is one Python module, a thousand-something lines, and it
> runs at a locked **60 frames per second**.

*Press SPACE to start. Game begins running.*

---

## 3. Live Demo — Movement  (~40 s)

*Player auto-runs to the right. Demonstrate inputs in order.*

> **SAY:** Movement is the whole game, so we made it feel *good*.  [beat]
> *(press Space)* Single jump.
> *(press Space again mid-air)* Double-jump — with a slight cut-off so it
> rewards skilled timing.
> *(press Shift)* Dash. It's a short invulnerability window — you can dash
> *through* enemies and hazards if you read the room.
> *(hold S while running)* Slide. Dips your hitbox under low ceilings and
> picks up a momentum boost.  [pause]
> *(hop onto a wall and hold direction)* Wall-slide. *(press Space)*
> Wall-jump.  [beat]  Coyote time, jump-buffering, air-control — all the
> little tricks modern platformers use to feel *responsive*. They're all in.

---

## 4. Live Demo — Threats & Tools  (~30 s)

*Continue running. Encounter spikes, an automaton, a crumble tile.*

> **SAY:** The world fights back.  [beat]
> Spikes punish lazy jumps. Crumble tiles collapse the moment you land.
> Steam vents launch you skyward. Automatons patrol — and stomp damage
> *refunds* an air jump, so chaining them feels great.  [pause]
> *(press E for glyph-bomb)* And this is your *answer* — the glyph-bomb.
> A throwable arcane charge that clears space, opens routes, and just
> looks cool.

---

## 5. Systemic Design — the cool part  (~30 s)

*Camera continues scrolling through new terrain.*

> **SAY:** Here's the part I'm proudest of: **nothing is hand-placed.**
> [beat]
> The world is stitched together at runtime from a library of small
> hand-authored *chunks* — little 30-tile-wide rooms — that get picked,
> mirrored, and threaded so the entrance of the next chunk always lines up
> with the exit of the last one.  [pause]
> The game gets harder by *biasing* which chunks the picker can choose,
> and by ramping the auto-scroll speed with distance. So the difficulty
> curve is emergent, not scripted — every run is genuinely different,
> but never unfair.

---

## 6. Why Python?  (~20 s)

*Show the file tree or open `game/world.py` briefly.*

> **SAY:** "Why Python for a 60-FPS action game?" — fair question.  [beat]
> Because the constraint *is* the design. Pygame forces you to write tight,
> deliberate code. There's no scene graph hiding the work for you.
> Every pixel on screen is the result of a function call you wrote.  [pause]
> And honestly? It ships as a single executable through PyInstaller.
> One `build.bat` and you have a portable game. That's it.

---

## 7. The Close — call to action  (~15 s)

*Return to game. Player dies — Game Over screen comes up.*

> **SAY:** *(gestures at score)* That run was — *(reads number)* meters.
> [beat]  Your turn.  [pause]
> **Babel's Glyph.** Run far. Die loud. Rewrite the past.  [beat]
> Thank you.

*Smile. Wait for applause. Take questions.*

---

## Speaker Notes

- **Energy curve:** start *quiet* in the cold open, build to *loud* during
  the trailer, drop to *calm-confident* for the technical pitch, back up to
  *playful-energetic* during the live demo, and land *quiet-bold* on the
  closing line.
- **If the live demo dies early:** press `R` mid-sentence — restart is
  instant and lets you keep talking without breaking flow.
- **If something visually amazing happens unscripted** (a wall-jump combo,
  a near-miss on spikes), call it out: *"See that? — that's the game
  playing itself."* Don't fight the improv; lean into it.
- **Backup line** if a feature won't trigger: *"You'll have to take my
  word for it — or play it yourself after the talk."*

---

## Quick-reference cue card

| Section            | Visual                       | One-line cue                                      |
|--------------------|------------------------------|---------------------------------------------------|
| Cold open          | Title screen / trailer paused | "Imagine the great library of Babel."             |
| Trailer            | 30-s promo plays             | "outrunning history itself"                       |
| Pitch              | Title screen                 | "hand-crafted in Python and pygame"               |
| Movement demo      | Live game                    | jump, double-jump, dash, slide, wall-jump         |
| Threats demo       | Live game                    | spikes, crumble, steam, automatons, glyph-bomb    |
| Systemic design    | Game scrolling               | "nothing is hand-placed"                          |
| Tech choice        | File tree                    | "the constraint *is* the design"                  |
| Close              | Game-over screen             | "Run far. Die loud. Rewrite the past."            |
