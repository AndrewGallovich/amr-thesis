import numpy as np
from gnuradio import gr

LOW = [697, 770, 852, 941]           # row tones
HIGH = [1209, 1336, 1477, 1633]      # column tones
KEYS = [['1', '2', '3', 'A'],
        ['4', '5', '6', 'B'],
        ['7', '8', '9', 'C'],
        ['*', '0', '#', 'D']]


class blk(gr.sync_block):
    def __init__(self, sample_rate=25000):
        gr.sync_block.__init__(
            self,
            name='Touch-tone (DTMF) decoder',
            in_sig=[np.float32],   # FM audio
            out_sig=None
        )
        self.fs = int(sample_rate)
        self.win = int(0.025 * self.fs)   # look at 25 ms at a time
        self.hop = int(0.010 * self.fs)   # ...every 10 ms
        n = np.arange(self.win)
        hann = np.hanning(self.win)
        # one "detector" per tone: how much of that exact frequency is present
        self.probes = {f: hann * np.exp(-2j * np.pi * f * n / self.fs) for f in LOW + HIGH}
        self.buf = np.zeros(0, dtype=np.float32)
        self.current = None      # key seen in the last window
        self.count = 0           # how many windows in a row
        self.emitted = False
        self.quiet = 0           # windows since the last key
        self.digits = ''

    def detect(self, s):
        s = s - s.mean()
        total = np.sum(s * s) + 1e-12
        p = {f: abs(np.dot(s, self.probes[f])) ** 2 for f in LOW + HIGH}
        lo = sorted(LOW, key=lambda f: p[f], reverse=True)
        hi = sorted(HIGH, key=lambda f: p[f], reverse=True)
        # a real key = one clearly strongest low tone AND one clearly strongest high tone
        if p[lo[0]] < 3 * p[lo[1]] or p[hi[0]] < 3 * p[hi[1]]:
            return None
        # ...and those two tones are a big part of the sound (not just noise)
        energy = (p[lo[0]] + p[hi[0]]) * 8 / (self.win * self.win)
        if energy < 0.2 * total / self.win:
            return None
        return KEYS[LOW.index(lo[0])][HIGH.index(hi[0])]

    def work(self, input_items, output_items):
        self.buf = np.concatenate([self.buf, input_items[0]])
        while len(self.buf) >= self.win:
            key = self.detect(self.buf[:self.win])
            self.buf = self.buf[self.hop:]
            # Step 1: a key counts once it has been heard 4 windows in a row (~40 ms)
            if key is not None and key == self.current:
                self.count += 1
            else:
                self.current, self.count, self.emitted = key, 1, False
            if key is not None:
                self.quiet = 0
                if self.count >= 4 and not self.emitted:
                    self.digits += key
                    self.emitted = True
            else:
                # Step 2: after ~0.5 s with no key, print the whole number
                self.quiet += 1
                if self.quiet == 50 and self.digits:
                    print(f"DTMF: {self.digits}", flush=True)
                    self.digits = ''
        return len(input_items[0])
