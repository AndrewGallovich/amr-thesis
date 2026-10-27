# GRCon26 CTF: Signal ID (notes)

## The challenge

- One recording (`sigid.sigmf-data`), 90 s long, 500,000 samples per second.
- It's a **synthetic mix**: lots of different signals side by side, like a radio dial with many stations playing at once.
- The center frequency in the metadata (4.625 MHz) is just decoration. Identify each signal from what it looks like, not from what band it's on.
- **11 carriers, 14 flags**, so some carriers hold more than one flag.

### How to submit (this tripped me up)

- Format is **`flagN{...}`**: the flag's number goes in the prefix, e.g. `flag7{...}`.
- **Each flag goes in its own challenge:** Signal ID 1 only takes `flag1{...}`, Signal ID 7 only takes `flag7{...}`, and so on. The recording is attached to Signal ID 1, but there are 14 separate entries.
- Some carriers can't say `flag{` (e.g. a voice). If you get a bare value, wrap it yourself: `flagN{VALUE}`.

## Progress

| Flag | Carrier | How | Value | Submitted |
|---|---|---|---|---|
| 6 | −140 kHz FM stereo | Voice, one stereo channel | (add) | ✅ |
| 7 | −140 kHz FM stereo | Voice, other stereo channel, NATO phonetic | `flag7{DUGA}` | ✅ |
| 8 | −140 kHz FM stereo | RDS RadioText | `flag8{THE_PIP}` | ✅ |

**1 of 11 carriers done, 3 of 14 flags.**

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

## Thesis link

Rules an automatic classifier could use:

- Center spike that spreads with content + comb of lines → FM.
- FM + spike at 19 kHz → broadcast stereo, decode both channels.
- Double hump at 57 kHz → RDS (BPSK) data.
- Solid vs. dashed in the waterfall → continuous vs. bursty: an easy first feature.
- RDS showed the "detect → demodulate → look again" loop: a BPSK signal hidden *inside* an FM signal.
