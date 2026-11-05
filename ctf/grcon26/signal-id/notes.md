# GRCon26 CTF: Signal ID (notes)

## The challenge

- One recording (`sigid.sigmf-data`), 90 s long, 500,000 samples per second.
- It's a **synthetic mix**: lots of different signals side by side, like a radio dial with many stations playing at once.
- The center frequency in the metadata (4.625 MHz) is just decoration. Identify each signal from what it looks like, not from what band it's on.
- **11 carriers, 14 flags**, so some carriers hold more than one flag.
- **Theme: famous mystery radio stations.** UVB-76 ("The Buzzer") really broadcasts on 4625 kHz, hence the metadata. MDZHB is the Buzzer's later call sign. Other flags so far: DUGA (Soviet "Russian Woodpecker" radar), The Pip, the Lincolnshire Poacher, Sky King (US military shortwave broadcasts that start "Skyking, Skyking, do not answer"), Woodpecker (the nickname for the DUGA radar's tapping sound), Swedish Rhapsody (a Polish numbers station named after the music-box tune it played). If a flag is half-heard, guess from the theme.

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
| 9 | +80 kHz FM + 1200/2200 Hz tones | Packet radio (AFSK 1200), decoded by Python block | `flag9{WOODPECKER}` | ✅ |
| 10 | +110 kHz two-frequency FSK | Pager (POCSAG), decoded by Python block | `flag10{SWEDISH_RHAPSODY}` | ✅ |
| 11 | +140 kHz two-frequency FSK, 1600 bits/s | Pager (FLEX), decoded by Python block | `flag11{YOSEMITE_SAM}` | ✅ |

**8 of 11 carriers done, 10 of 14 flags.** Left: flags 5, 12–14 (carriers at about +170, +200, +225 kHz).

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

## Carrier: +80 kHz = packet radio (flag 9)

### How I knew

1. **Zoomed waterfall:** a steady line at 0 plus faint dashed lines at ±1.1 and ±2.2 kHz, evenly spaced, mirror images, blinking together → **one signal**, a carrier with something switched on and off on top.
2. **AM or FM?** Ran both detectors side by side:
   - Complex to Mag (loudness): flat ~0.05 with tiny random jitter → nothing there.
   - Quadrature Demod (pitch): big regular wave, −2 to +2 → **FM**.
   - **Read the numbers on the axis, not the shape.** Autoscale makes noise look as busy as a real signal.
3. **Listening:** "tones, then static." The static is just the gaps between messages.
4. **Inside each burst:** two pitches, **~1200 Hz and ~2200 Hz**, switching at **1200 times per second** (0.83 ms per bit). That's the **Bell 202** standard = **packet radio** (APRS), sending bits as two audio tones (AFSK).

So it's **FM carrying a two-tone modem signal**. Bursts last ~0.5 s and repeat every ~1.3 s, all with the same message.

### Chain

```
Xlating (offset 80000, bw 8000, decim 50 → 10 kHz)
  → Quadrature Demod (gain 1)                          ← FM → audio tones
  → Xlating (Float→Complex, center 1700, decim 1,
             taps firdes.low_pass(1, samp_rate/decim, 1200, 300))
  → Quadrature Demod (gain 1)                          ← tones → high/low
  → Rational Resampler (interp 6, decim 5 → 12 kHz)    ← exactly 10 samples per bit
  → Symbol Sync (Float, Gardner, SPS 10, loop BW 0.01, output SPS 1)
  → Binary Slicer                                      ← high = 1, low = 0
  → Embedded Python Block "Packet radio decoder"
```

- The **second Quadrature Demod** is the trick: measuring pitch again turns low beep / high beep into two levels (±0.33), a clean staircase.
- Centering it at **1700 Hz** = halfway between the two tones.
- Time Sink can't show bytes: put **Char To Float** between the Binary Slicer and the Time Sink.

### How the Python block decodes it

1. **NRZI:** the bit isn't the level, it's whether the beep **changed**. Changed = 0, stayed = 1. (Same idea as RDS's Differential Decoder.)
2. **HDLC framing:** each message starts and ends with the marker `01111110`. The sender inserts a filler 0 after five 1s in a row so data never looks like the marker; the block removes those.
3. **Bytes + error check:** every 8 bits = 1 byte (least significant bit first). The last 2 bytes are a CRC-16 error check; only messages that pass are printed.
4. **AX.25 addresses:** receiver (7 bytes), sender (7 bytes), each letter shifted left by 1 bit. Then 2 control bytes, then the text.

Output: `NUMBRS > APZ001: >flag9{WOODPECKER}`

## Carrier: +110 kHz = pager, POCSAG (flag 10)

### How I knew

1. **Wider than the others** (~10 kHz in the big waterfall, a zigzag). Needed `decim = 25` (view ±10 kHz) and `bw = 15000`.
   - **Lesson:** `bw` must fit inside the view. With `decim = 50` (±5 kHz) and `bw = 15000`, the extra wrapped around and smeared everything (aliasing).
   - Also had to switch the taps back from the sideband filter to `firdes.low_pass(...)` again.
2. **Zoomed waterfall:** two bands at about **±4.5 kHz**, nothing in the middle, coming in bursts.
3. **Quadrature Demod → Time Sink:**
   - At 10 ms: a smooth **600 Hz** wave = alternating bits 1010… (the pager "wake-up" pattern). One bit = 0.83 ms → **1200 bits/s**.
   - At 500 ms: flat at **+1.7 or −1.7**, jumping between them = **two-frequency FSK** (bits sent by jumping between two radio frequencies, no audio step).
4. ±4.5 kHz shift + 1200 bits/s + long 1010 wake-up = **POCSAG**, the standard pager format.

- Not the pulse dial (Hint 5): a rotary dial clicks only ~10 times per second with pauses between digits. This switched dozens of times per 100 ms.

### Chain

```
Xlating (offset 110000, bw 15000, decim 25 → 20 kHz)
  → Quadrature Demod (gain 1)                          ← the two frequencies → two levels
  → Rational Resampler (interp 3, decim 5 → 12 kHz)    ← exactly 10 samples per bit
  → Symbol Sync (Float, Gardner, SPS 10, loop BW 0.01, output SPS 1)
  → Binary Slicer
  → Embedded Python Block "Pager (POCSAG) decoder"
```

Same as flag 9 but **without** the audio step (one Quadrature Demod, not two).

### How the Python block decodes it

1. **Find the marker** `0x7CD215D8` ("a batch starts here"). Also checks the flipped version, in case 0s and 1s are upside down.
2. **Read 16 words of 32 bits**, then expect the marker again.
3. **First bit of each word:** 0 = **address** (which pager), 1 = **20 bits of message**. `0x7A89C197` = filler ("nothing to send").
4. **Text:** letters are 7 bits each (least significant bit first), digits 4 bits each. The block prints both; only one makes sense.

Plain bits, no "did it change?" rule (unlike packet radio and RDS).

Output: `flag10{SWEDISH_RHAPSODY}`

## Carrier: +140 kHz = pager, FLEX (flag 11)

### How I knew (and the wrong turn)

1. **Widest one yet** (~135–147 kHz). Needed `decim = 20` (view ±12.5 kHz) with `bw = 20000`.
2. **Zoomed waterfall:** two strong lines at **±4.9 kHz**, empty middle, "ladder rungs" between them in the big waterfall → two-frequency FSK again.
3. **Quadrature Demod → Time Sink (400 ms):** clean two levels with steps that looked like **5 ms** → I guessed **200 bits/s**. **This was wrong.**
4. At 200 bits/s the bits had a repeating 13-bit pattern but matched no format (serial text, change-encoding, digit codes, Manchester…).
5. **Different approach:** recorded the Quadrature Demod output to a WAV and looked at it **zoomed in to 0.1 ms**. The message parts flip every **0.625 ms** → **1600 bits/s**. At 200 we were reading only 1 bit in 8.
6. 1600 bits/s + ±4.8 kHz + everything repeating every **1.875 s** = **FLEX**, the newer paging system. Its frame marker turned up exactly once per 1.875 s.

**Lessons:**
- **A Time Sink zoomed out can hide fast data.** Long flat steps were real, but the fast parts in between were too squashed to see. Measure the *shortest* step at a zoom where you can see individual samples.
- When bits make no sense in any format, **suspect the bit rate before the format**.

### Chain

```
Xlating (offset 140000, bw 20000, decim 20 → 25 kHz)
  → Quadrature Demod (gain 1)
  → Rational Resampler (interp 16, decim 25 → 16 kHz)   ← exactly 10 samples per bit at 1600
  → Symbol Sync (Float, Gardner, SPS 10, loop BW 0.01, output SPS 1)
  → Binary Slicer
  → Embedded Python Block "FLEX pager decoder"
```

### How the Python block decodes it

1. **Marker** in the middle of the frame header (`0xA6C6AAAA`, or flipped). Then skip 16 filler bits + the 32-bit frame info word + 40 more filler bits.
2. **Un-shuffle ("interleaving"):** each 256-bit block holds 8 words of 32 bits, sent **one bit from each word in turn**, so a burst of noise only damages one bit per word. 11 blocks = 88 words.
3. Each word = 21 data bits + 10 check bits (BCH error check) + 1 parity bit. All 88 words passed the check.
4. **Table of contents:** word 0 says where the **address** (which pager) and the **vector** (what kind of message, where, how long) are. In this frame: address in word 1, vector in word 2, message in words 3–11. Pager number 1234567, type 5 = letters.
5. **Letters:** 3 per word, 7 bits each.

- Quirk: in this file the data bits use the **opposite** 0/1 sense to the marker.

Output: `flag11{YOSEMITE_SAM}`

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
- Steady carrier + symmetric sidebands at a tone spacing → something switched on top. Try both AM and FM detectors; the one with a regular pattern (not random jitter) wins.
- FM audio with two tones at 1200/2200 Hz, 1200 bits/s → packet radio (AFSK). Another "demodulate, then look again" case.
- Two bands mirrored around an empty middle + Quadrature Demod jumping between two flat levels → two-frequency FSK. ±4.5 kHz at 1200 bits/s with a 1010 wake-up → POCSAG pager.
- Short vs. long views tell different stories: 10 ms showed a smooth wave, 500 ms showed two levels. A classifier should look at more than one time scale.
- Two-frequency FSK at ±4.8 kHz: 1200 bits/s with a 1010 wake-up → POCSAG; 1600 bits/s with 1.875 s frames → FLEX. **Symbol rate** and **frame timing** are the features that separate them, not the spectrum.
- Estimate the bit rate from the **shortest** run at fine zoom (or from the spectrum of the demodulated signal), never from a zoomed-out picture.
- Dashed line + flat on/off blocks in the strength + two "on" lengths at 1 : 3 → on/off keying, Morse.
- ~2.4 kHz wide, energy on one side only, sharp edge at ±0.3 kHz → SSB voice. Energy right of the edge → USB; energy left of the edge → LSB.
- Spikes ~10 ms apart in the strength → speech.
- Strength alone isn't enough: a smooth hill meant "check frequency." A classifier needs both **strength over time** and **frequency over time** features.
- My Morse decoder hard-codes the 65 ms unit. A real classifier should measure the unit itself (e.g. from the shortest common on-time).
