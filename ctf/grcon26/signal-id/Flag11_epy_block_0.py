import numpy as np
from gnuradio import gr

MARK = 0xA6C6AAAA          # middle of the FLEX frame marker
SYNC2_BITS = 40            # 25 ms of filler after the frame header (at 1600 bits/s)
DATA_BITS = 88 * 32        # 11 blocks x 8 words x 32 bits
NUMERIC = '0123456789 U -]['


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='FLEX pager decoder',
            in_sig=[np.uint8],   # one 0/1 per bit (1600 bits/s), from the Binary Slicer
            out_sig=None         # prints to the console
        )
        self.reg = 0             # last 64 bits, to spot the frame marker
        self.state = 'hunt'
        self.invert = 0
        self.count = 0
        self.words = [0] * 88

    def work(self, input_items, output_items):
        for b in input_items[0]:
            b = int(b)
            if self.state == 'hunt':
                # Step 1: find the frame marker (or its flipped version)
                self.reg = ((self.reg << 1) | b) & 0xFFFFFFFFFFFFFFFF
                mid = (self.reg >> 16) & 0xFFFFFFFF
                if mid in (MARK, MARK ^ 0xFFFFFFFF):
                    self.invert = 0 if mid == MARK else 1
                    self.state = 'skip'
                    self.count = 16 + 32 + SYNC2_BITS   # 16 filler + frame info word + filler
            elif self.state == 'skip':
                self.count -= 1
                if self.count == 0:
                    self.state = 'data'
                    self.words = [0] * 88
            else:
                # Step 2: un-shuffle the bits. Each block of 256 bits holds 8 words,
                # sent one bit from each word in turn ("interleaving").
                bit = b ^ self.invert ^ 1   # data bits use the opposite sense to the marker
                c = self.count
                word = (c >> 8) * 8 + (c & 7)
                pos = (c >> 3) & 31
                self.words[word] |= bit << pos        # first bit sent = smallest bit
                self.count += 1
                if self.count == DATA_BITS:
                    self.decode([w & 0x1FFFFF for w in self.words])  # keep 21 data bits
                    self.state = 'hunt'
                    self.reg = 0
        return len(input_items[0])

    # Step 3: read the frame's table of contents, then each message
    def decode(self, w):
        biw = w[0]                             # first word: where things are
        if biw in (0, 0x1FFFFF):
            return
        aoffset = ((biw >> 8) & 0x3) + 1       # where the addresses start
        voffset = (biw >> 10) & 0x3F           # where the "vectors" start
        if not aoffset < voffset <= 88:
            return
        for i in range(aoffset, voffset):
            j = voffset + (i - aoffset)        # each address has a matching vector
            if j >= 88:
                break
            addr = w[i] - 0x8000               # pager number
            vec = w[j]
            kind = (vec >> 4) & 0x7            # 5 = letters, 3/4/7 = digits
            start = (vec >> 7) & 0x7F          # where the message words are
            length = (vec >> 14) & 0x7F
            msg = w[start:start + length]
            if not msg:
                continue
            # Letters: 3 x 7 bits per word. Digits: 4 bits each.
            letters = ''.join(chr((m >> s) & 0x7F) for m in msg for s in (0, 7, 14))
            letters = ''.join(c for c in letters if 32 <= ord(c) < 127)
            bits = ''.join(format(m, '021b')[::-1] for m in msg)
            digits = ''.join(NUMERIC[int(bits[k:k + 4][::-1], 2)]
                             for k in range(0, len(bits) - 3, 4))
            print(f"Pager {addr} (type {kind}):", flush=True)
            print(f"   as letters: {letters}", flush=True)
            print(f"   as digits:  {digits.strip()}", flush=True)