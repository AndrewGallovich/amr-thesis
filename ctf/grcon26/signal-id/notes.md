# GRCon26 CTF: Signal ID (notes)

## The challenge

- One recording (`sigid.sigmf-data`), 90 s long, 500,000 samples per second.
- It's a **synthetic mix**: lots of different signals side by side, like a radio dial with many stations playing at once.
- The center frequency in the metadata (4.625 MHz) is just decoration. Identify each signal from what it looks like, not from what band it's on.
- **11 carriers, 14 flags**, so some carriers hold more than one flag.
- **Theme: famous mystery radio stations.** UVB-76 ("The Buzzer") really broadcasts on 4625 kHz, hence the metadata. MDZHB is the Buzzer's later call sign. Other flags so far: DUGA (Soviet "Russian Woodpecker" radar), The Pip, the Lincolnshire Poacher, Sky King (US military shortwave broadcasts that start "Skyking, Skyking, do not answer"). If a flag is half-heard, guess from the theme.

### How to submit (this tripped me up)

- Format is **`flagN{...}`**: the flag's number goes in the prefix, e.g. `flag7{...}`.
- **Each flag goes in its own challenge:** Signal ID 1 only takes `flag1{...}`, Signal ID 7 only takes `flag7{...}`, and so on. The recording is attached to Signal ID 1, but there are 14 separate entries.
- Some carriers can't say `flag{` (e.g. a voice). If you get a bare value, wrap it yourself: `flagN{VALUE}`.

## Progress

| Flag | Carrier | How | Value | Submitted |
|---|---|---|---|---|
| 1 | −20 kHz on/off keying | Morse code, decoded by Python block | `flag1{UVB76}` | ✅ |
| 2 | +25 kHz USB voice | Upper sideband voice | `flag2{POACHER}` | ✅ |
| 3 | +5 kHz LSB voice | Lower sideband voice | `flag3{CHERRY}` | ✅ |
| 4 | +50 kHz narrowband FM | FM-demodulated voice (`Flag4.grc`) | `flag4{SKYKING}` | ✅ |
| 6 | −140 kHz FM stereo | Voice, one stereo channel | `flag6{MDZHB}` | ✅ |
| 7 | −140 kHz FM stereo | Voice, other stereo channel, NATO phonetic | `flag7{DUGA}` | ✅ |
| 8 | −140 kHz FM stereo | RDS RadioText | `flag8{THE_PIP}` | ✅ |

**5 of 11 carriers done, 7 of 14 flags.** Left: flags 5, 9–14.

Flag 2 was heard as "P_ACHER"; the missing letter is O (Lincolnshire Poacher, a British numbers station).

## Step 1: Look at everything

**Blocks:** File Source → Throttle → Frequency Sink + Waterfall Sink (bandwidth `samp_rate`).

- **Frequency Sink:** shows *where* the signals are (left of center = negative offset). It's one moment in time.
- **Waterfall:** left to right is frequency, bottom to top is time, color is strength (yellow = noise, red = strong). It's many Frequency Sink snapshots stacked up.

| Waterfall shape | Means |
|---|---|
| Solid vertical line | Always on |
| Dashed vertical line | Switching on/off (bursts, Morse, packets) |
| Short horizontal streak | Got wide for a moment (FM getting loud) |
| Slanted line | Drifting frequency |
| Zigzag / jumping | Frequency hopping |

**Lesson: peaks ≠ signals.** One signal can make several peaks (the FM station made about 7). Group lines that are:
- **evenly spaced**,
- **symmetric** around a center,
- and **change together** (horizontal streaks cross all of them at once).

That's one signal.

## Step 2: Tune in to one signal

**Block:** Frequency Xlating FIR Filter, plus sliders:

- `offset`: the tuning knob (which signal).
- `bw`: how wide you listen around it.
- `decim`: shrinks the data after tuning.

**Lesson:** set `bw` from the signal's **widest** shape. Too narrow cuts the signal off; too wide lets neighbors in. One signal looks **symmetric**; a neighbor shows up as an extra bump on one side.

**Xlating filter settings that must be right** (I got these wrong at first):
- Center Frequency = `offset` (not `0`, or the slider does nothing).
- Decimation = `decim` (not `1`, or every sink after it shows the wrong time/frequency scale).
- Units: `offset` is in Hz. −20 kHz is `-20000`, not `-20`.
- Taps: `firdes.low_pass(1, samp_rate, bw/2, bw/10)` for normal use. Change them back after using a special filter (e.g. the sideband ones below), or the next signal gets blocked.
- With `decim = 50`, the output is 10,000 samples per second, so keep `bw` under ~8000.

## Step 3: Look at the tuned signal

Add these **after the Xlating filter** (all at rate `samp_rate/decim`):

| Block | Shows | Use it for |
|---|---|---|
| Waterfall Sink (Complex, bw `samp_rate//decim`) | Zoomed waterfall of just this signal | Is it centered? One-sided? Jumping? Sliding? |
| Complex to Mag → Time Sink (Float) | Strength over time | On/off patterns, pulse lengths |
| Complex to Real → Multiply Const → WAV File Sink | Audio | Listening to voices and beeps |

- **Feed the zoomed waterfall from the Xlating filter, not from Complex to Mag.** Magnitude throws away frequency, so it just shows a line at 0.
- **Time Sink:** Number of Points `10000` (1 s at 10k). Turn on Autoscale (right-click the plot, or set it in the block), or set Y min `0` since magnitude is never negative.
- **Too fast to see:** right-click the plot → Stop to freeze it; Throttle at `samp_rate/10` slows the playback; Update Period `1`.
- **WAV sink sample rate must be a whole number:** `samp_rate//decim` (`//` = integer division; `/` gives 10000.0, which it rejects).
- Signals here are tiny (~0.01–0.05), so Multiply Const `25`–`50` before the WAV, but not so high it clips.
- Audacity cleanup: select a silent bit → Noise Reduction → Get Noise Profile, then select all → Noise Reduction, then Normalize.

### Reading the Time Sink

| What I saw | Meant |
|---|---|
| Random fuzz around ~0.01 | Noise: off-tune, filter too wide, or caught an "off" moment |
| Flat blocks, sharp edges, fully on or off | On/off keying (Morse) |
| Smooth hill, rises and fades | Signal sliding through a narrow filter: widen `bw` and look at the zoomed waterfall |
| Bursts of evenly spaced spikes ~10 ms apart | Voiced speech (each spike = a vocal-cord puff, ~100/s) |

## Carrier: +50 kHz = narrowband FM voice (flag 4)

- In the big waterfall: a **solid** red line at +50 kHz (always on).
- **Narrowband FM (NBFM)** = the same idea as the FM radio station, but only a few kHz wide. It's what walkie-talkies and two-way radios use for voice. No stereo, no RDS.

**Chain** (`Flag4.grc`):

```
Xlating (center 50000, bw 10000, decim 50 → 10 kHz)
  → Quadrature Demod (gain 1)
  → Rational Resampler (interp 4, decim 5 → 8 kHz)
  → WAV File Sink (8000)
```

- Center Frequency is typed in as `50000` instead of `offset`, and the WAV path is hard-coded to `~/Downloads/New.wav`. Switch both to `offset` / `base` so it works on both machines.
- The hints say another NBFM slot holds the **telephone pulse dial**, so this same chain should work there too.

## Carrier: −20 kHz = Morse code (flag 1)

### How I knew

- In the big waterfall: a **dashed** line (switching on and off).
- Time Sink after Complex to Mag (`bw = 1000`): **flat on-blocks with sharp edges**.
- Two lengths of "on" at about **1 : 3** (~60 ms and ~195 ms), and gaps of about 1, 3, and 7 units. That's exactly Morse timing.

| Part | Length | Measured |
|---|---|---|
| Dot | 1 unit | ~60 ms |
| Dash | 3 units | ~195 ms |
| Gap inside a letter | 1 unit | ~70 ms |
| Gap between letters | 3 units | ~210 ms |
| Gap between words | 7 units | extra-long silence |

Unit ≈ 65 ms, about 18 words per minute.

**Debugging lesson:** with `bw = 10000` I only saw noise. These lines are faint, so a wide filter buries them. `bw = 1000` made the blocks clear.

**Listening trick:** set `offset = -20000 + 700` and `bw = 2000`. The carrier lands at 700 Hz and becomes an audible beep in the WAV.

### Automatic decoder

**Chain:** Xlating (`offset -20000`, `bw 1000`) → Complex to Mag → Moving Average (length `100`, scale `1/100`, smooths the edges) → Embedded Python Block "Morse decoder" (`samp_rate//decim`, threshold `0.006`, unit `65`).

How the block works:
1. **Threshold:** above 0.006 = on (halfway between on ~0.01 and off ~0.002).
2. **Run lengths:** count samples in each on/off stretch, convert to units (ms ÷ 65).
3. **Classify:** on < 2 units = dot, else dash. Off < 2 = same letter; 2–5 = new letter; ≥ 5 = new word.
4. **Look up** the dot/dash group in a Morse table and print it.

Tuning: lots of `?` → try threshold `0.005`/`0.007`. Wrong spacing → unit 60–70. The table has no hyphen, so "UVB-76" would print as `UVB?76`.

Output: `FLAG 1 IS UVB76` → `flag1{UVB76}`.

## Carriers: +5 kHz and +25 kHz = single sideband voice (flags 3 and 2)

These were the "middle" and "right" dashed lines next to the Morse one. All three turned out to be **separate carriers** with different patterns.

### How I knew

- First Time Sink looked like a **smooth hill**, not on/off blocks. That meant "look at frequency, not just strength."
- Zoomed waterfall (`bw = 5000`): energy **on only one side** of 0, about **2.4 kHz wide** (phone-quality voice), with a **sharp edge at ±0.3 kHz** and nothing on the other side.
- Time Sink: bursts of evenly spaced spikes = speech.

**SSB (single sideband):** normal AM sends the carrier plus two mirror-image copies of the voice. SSB keeps only one copy, saving power and bandwidth. The sharp edge is where the voice's lowest pitches (~300 Hz) sit, just next to the missing carrier.

| | +5 kHz (flag 3) | +25 kHz (flag 2) |
|---|---|---|
| Energy | Left of 0 | Right of 0 |
| Sharp edge | −0.3 kHz | +0.3 kHz |
| Type | **LSB** (lower sideband) | **USB** (upper sideband) |
| Taps | `firdes.complex_band_pass(1, samp_rate, -2800, -300, 200)` | `firdes.complex_band_pass(1, samp_rate, 300, 2800, 200)` |

**Demodulating:** with the missing carrier tuned to exactly 0, **Complex to Real turns the sideband straight back into audio**. Chain: Xlating (one-sided taps) → Complex to Real → Multiply Const `25` → WAV.

- First try used the normal ±2.5 kHz filter: the voice was there but buried. Complex to Real folds the **empty side's noise** on top of the voice. The one-sided band-pass blocks it.
- If the voice sounds like a duck or muffled, nudge `offset` by ±100 Hz.

## Carrier: −140 kHz = FM broadcast stereo (flags 6, 7, 8)

### How I knew it was FM

1. **Comb of evenly spaced lines** in the waterfall. FM carrying a steady tone makes copies spaced by that tone (here 19 kHz).
2. It **spreads out when loud** and shrinks to a spike in silence. FM stores sound in how far the frequency swings.
3. It's the **width of an FM radio station**.
4. **Spikes at ±19 kHz**: the stereo pilot tone, only used by FM broadcast.

### What's inside an FM stereo station

Once you FM-decode it (Quadrature Demod), the output is a stack of parts. These frequencies are **the worldwide standard**, not specific to this file:

| Frequency | Part | Notes |
|---|---|---|
| 0–15 kHz | Mono audio (L+R) | Every radio plays this |
| **19 kHz** | Pilot tone | Says "I'm stereo" + timing reference |
| **38 kHz** (2 × 19) | Stereo part (L−R) | No spike; just a low lump. Its tone is removed to save power |
| **57 kHz** (3 × 19) | RDS data | Digital text: station name, RadioText |

- The decoder output is **real (float)**, so its spectrum is a mirror image. Only read 0 Hz and up.
- **Pilot tone's two jobs:** (1) tells the radio to switch on stereo; (2) the radio doubles it to get an exactly lined-up 38 kHz (triples for 57 kHz). It sits at 19 kHz because that's an empty gap between the audio and the stereo part, and it's mostly inaudible.

### Flags 6 & 7: the two voices (stereo)

- **Mono decode** (Quadrature Demod → Resampler → WAV) gave **two voices talking over each other**: one on Left, one on Right, mixed together.
- **Stereo, simply:** the station sends L+R plus L−R hidden at 38 kHz. Multiply by your own 38 kHz wave, low-pass it, then **Left = (L+R) + (L−R)**, **Right = (L+R) − (L−R)**.

**Why the built-in WBFM Receive PLL block failed:** your 38 kHz wave has to be **lined up** with the hidden one. It's like pushing a swing: in time, it works; a quarter-swing late, it cancels to zero. The block's alignment is fixed in its code (Complex to Imag). This file is lined up a quarter-turn differently, so the block gets zero stereo and outputs mono on both sides. No setting fixes it.

**What worked: 7 blocks** (`decim = 2`, `bw = 180000`)

```
                  ┌→ LPF ───────────────┬→ Add ──→ left.wav
Xlating → Demod ──┤                     │
                  └→ Multiply → LPF ────┴→ Subtract → right.wav
                        ↑
               Signal Source (38 kHz, Cosine, amplitude 2)
```

- Quadrature Demod gain `1`. Both LPFs: decimation 10, cutoff 15 kHz, transition 3 kHz (audio at 25 kHz).
- The file is synthetic, so the pilot is perfectly steady and a plain Signal Source works (no pilot tracking needed).
- If voices still mixed: switch Cosine ↔ Sine. Changing `bw` shifts the alignment too.

**Flag 7 was in the NATO phonetic alphabet.** Each word = its first letter: Delta Uniform **Golf** Alpha → **DUGA**. ("Gold" was a mishearing of "Golf".) Wrap it yourself: `flag7{DUGA}`.

### Flag 8: RDS ("not audio at all", Hint 4)

**RDS (Radio Data System)** = the text a car radio shows (station name, song title). It's **BPSK at 1187.5 bits/s** on 57 kHz, and you can't hear it.

**Chain, starting from the Quadrature Demod:**

| # | Block | Settings | Why |
|---|---|---|---|
| 1 | Freq Xlating FIR Filter (Float→Complex) | Center `57000`, Sample Rate `samp_rate/decim`, Taps `firdes.low_pass(1, samp_rate/decim, 2400, 600)` | Move RDS to 0 Hz, cut everything else |
| 2 | Rational Resampler (Complex) | Interp `19`, Decim `250` → 19 kHz | Exactly **16 samples per bit** |
| 3 | Decimating FIR Filter (Complex, real taps) | Taps `[1]*8 + [-1]*8` | **Matched filter**: each RDS bit is "up then down" |
| 4 | Symbol Sync | Gardner, SPS `16`, loop BW `0.01`, output SPS `1` | Read each bit at the right moment |
| 5 | Constellation Receiver | BPSK, loop BW `2*math.pi/100` | Fix rotation, sample → 0/1 |
| 6 | Differential Decoder | Modulus `2` | RDS stores data as *changes* between bits |
| 7 | Embedded Python Block | "RDS text decoder" | Bits → text, printed to console |

**`firdes.low_pass(gain, sample_rate, cutoff, transition)`:**
- gain `1`;
- sample_rate = rate **going into** that filter;
- cutoff = how far to keep on **each side** of 0;
- transition = how sharply it goes from keep to block (smaller = sharper, slower).

**What I saw along the way:**
- After step 1: the **double hump** centered on 0, with a dip in the middle (that shape = digital, up-down bits).
- Time Sink after step 2: blue (real) has all the signal and red (imag) is ~0, which means **BPSK**. About one wiggle per bit (0.84 ms).
- After step 3: the signal got about 8× bigger, with clear peaks/dips once per bit.

**How the Python block decodes RDS:**
- A **group** = 4 blocks (A, B, C, D) × 26 bits = 104 bits.
- Each block = 16 data bits + 10 check bits, mixed with a different known pattern per block. All 4 checks pass = a full group arrived.
- Block B says the type: **0A** = 2 characters of the station name (PS); **2A** = 4 characters of RadioText (RT).
- Text fills in **out of order** because pieces arrive in rotation.

Output: `PS: [NUMBERS ]   RT: [flag8{THE_PIP}]`

### Why a Python block instead of the RDS blocks

- The RDS Decoder/Parser come from **gr-rds**, an add-on ("out-of-tree module"), not core GNU Radio.
- It's packaged for **apt** (`sudo apt install gr-rds`) but **not for conda-forge**, and an apt add-on won't work with conda's separate GNU Radio.
- An **Embedded Python Block** does the same job with nothing to install, and I can see exactly how bits become text.
- Keeping **conda** for the thesis: same environment on the ARM Mac VM and the x86 lab PC, GNU Radio + PyTorch together, and `environment.yml` makes it reproducible.

## Hints for what's ahead

- **Not everything is FM.** If a narrow data signal sounds like hiss through the FM demod, try a different detector (e.g. AM / Complex to Mag).
- **One narrowband FM slot is a telephone pulse dial** (from before touch-tones). Read the clicks in the **waveform** (Time Sink), not the spectrogram. The voice at the end isn't a flag.
- The challenge text says there's "a station reading groups": probably another numbers-station voice.
- Voice-like spikes ~10 ms apart are speech, not pulse dialing. Pulse dialing is about 10 clicks per second (~100 ms apart).

## Thesis link

Rules an automatic classifier could use:

- Center spike that spreads with content + comb of lines → FM.
- Same, but only a few kHz wide → narrowband FM (two-way radio voice).
- FM + spike at 19 kHz → broadcast stereo, decode both channels.
- Double hump at 57 kHz → RDS (BPSK) data.
- Solid vs. dashed in the waterfall → continuous vs. bursty: an easy first feature.
- RDS showed the "detect → demodulate → look again" loop: a BPSK signal hidden *inside* an FM signal.
- Dashed line + flat on/off blocks in the strength + two "on" lengths at 1 : 3 → on/off keying, Morse.
- ~2.4 kHz wide, energy on one side only, sharp edge at ±0.3 kHz → SSB voice. Energy right of the edge → USB; energy left of the edge → LSB.
- Spikes ~10 ms apart in the strength → speech.
- Strength alone isn't enough: a smooth hill meant "check frequency." A classifier needs both **strength over time** and **frequency over time** features.
- My Morse decoder hard-codes the 65 ms unit. A real classifier should measure the unit itself (e.g. from the shortest common on-time).
