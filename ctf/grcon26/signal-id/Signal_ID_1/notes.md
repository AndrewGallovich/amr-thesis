# GRCon26 CTF: Signal ID (notes)

## The challenge

- One recording (`sigid.sigmf-data`), 90 s long, 500,000 samples per second.
- It's a **synthetic mix**: lots of different signals placed side by side, like a radio dial with many stations playing at once.
- The center frequency in the metadata (4.625 MHz) is just decoration. You have to identify each signal from what it looks like, not from what band it's on.
- **11 carriers, 14 flags**, so some carriers hold more than one flag.
- Flag format: `flag{...}`. Some carriers just give a bare value; wrap it in `flag{}` yourself.

## Step 1: Look at everything

**Blocks:** File Source → Throttle → Frequency Sink + Waterfall Sink (both with bandwidth `samp_rate`).

- **Frequency Sink:** shows *where* the signals are (left of center = negative offset).
- **Waterfall:** shows *when* they're on. A solid line means it's always on; a dashed or blocky line means it's bursty.

**Lesson:** peaks ≠ signals. One signal can make several peaks (FM stereo made about 7, spaced 19 kHz apart), and faint signals can be easy to miss. Count *groups of lines that behave the same way* in the waterfall instead.

## Step 2: Tune in to one signal

**Block:** Frequency Xlating FIR Filter, plus two sliders:

- `offset`: the tuning knob (which signal).
- `bw`: how wide you listen around it.
- `decim`: shrinks the data after tuning, since you no longer need the full width.

**Lesson:** set `bw` from the signal's **widest** shape, not one moment. Too narrow cuts part of the signal off (the FM station looked like a thin spike until I widened it). Too wide lets neighbors in. One signal is **symmetric**; a neighbor shows up as an extra bump on one side.

## Signal: −140 kHz = FM broadcast stereo (3 flags)

**How I knew it was FM:**

1. It **spreads out** when there's sound and shrinks to a spike during silence. FM stores sound in how far the frequency swings.
2. It's about the **width of an FM radio station**.
3. **Spikes at ±19 kHz**: the 19 kHz **stereo pilot tone**, only used by FM broadcast. If you see FM with 19 kHz spikes, think stereo.

**Mono decode:** Quadrature Demod → Rational Resampler → WAV. Result: **two voices talking over each other** = two flags on the left and right channels, mixed together.

**How FM stereo works, simply:**

- The station sends **L+R** (normal sound) plus **L−R** hidden up at **38 kHz** (exactly 2 × the pilot).
- To recover L−R: multiply by your own 38 kHz wave, then low-pass filter.
- Then **Left = (L+R) + (L−R)** and **Right = (L+R) − (L−R)**.

**Why the WBFM Receive PLL block didn't work:**

- To pull out L−R, your 38 kHz wave has to be **lined up** with the hidden one. Like pushing a swing: in time, it works; a quarter-swing late, it cancels to zero.
- The block lines its wave up one fixed way (Complex to Imag in its code). This file is lined up a quarter-turn the other way, so the block gets **zero stereo** and outputs mono on both sides.
- No setting changes this. It's fixed in the block's code.

**What worked: 7 blocks**

```
                  ┌→ LPF ───────────────┬→ Add ──→ left.wav
Xlating → Demod ──┤                     │
                  └→ Multiply → LPF ────┴→ Subtract → right.wav
                        ↑
               Signal Source (38 kHz, Cosine, amplitude 2)
```

- Quadrature Demod gain `1`, `decim = 2`, `bw = 180000`.
- Both LPFs: decimation 10, cutoff 15 kHz, transition 3 kHz (audio comes out at 25 kHz).
- Because the file is synthetic, the pilot is perfectly steady, so a plain Signal Source works instead of tracking the pilot.
- If the voices are still mixed: switch the Signal Source from **Cosine** to **Sine**. Changing `bw` also shifts the alignment.
- File: `SigID1_stereo_simple.grc`

**Third flag on this station:** RDS data at 57 kHz in the decoded signal (the text a car radio shows). Not audio. Still to do.

## What the hints say is still ahead

- **Not everything is FM.** If a narrow data signal sounds like hiss through the FM demod, try a different detector (for example AM / Complex to Mag).
- **One narrowband FM slot is a telephone pulse dial** (from before touch-tones). Read the clicks in the **waveform** (Time Sink), not the spectrogram. The voice at the end isn't a flag.

## Thesis link

Rules an automatic classifier could use:

- Center spike that spreads with the signal's content → FM.
- FM + spike at 19 kHz → broadcast stereo, decode both channels.
- Extra content at 57 kHz → RDS data.
- Solid vs. dashed in the waterfall → continuous vs. bursty, an easy first feature.
