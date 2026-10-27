"""
RDS text decoder (replaces gr-rds RDS Decoder + RDS Parser).

Input: one bit per byte (0 or 1), straight from the Differential Decoder.
Prints the station name (PS) and RadioText (RT) to the console whenever they change.

How it works:
  RDS sends data in "groups" of 4 blocks (A, B, C, D), 26 bits each = 104 bits.
  Each block = 16 data bits + 10 check bits. The check bits are mixed with a
  known "offset word" that is different for A, B, C and D. So by checking the
  last 104 bits, we can tell when a full group has just arrived.
  Block B says what kind of group it is:
    type 0A -> 2 characters of the station name (PS, 8 chars total)
    type 2A -> 4 characters of RadioText (RT, up to 64 chars)
"""
import numpy as np
from gnuradio import gr

POLY = 0x5B9                              # RDS check polynomial (x^10+x^8+x^7+x^5+x^4+x^3+1)
OFFSETS = {0x0FC: 'A', 0x198: 'B', 0x168: 'C', 0x350: 'C', 0x1B4: 'D'}


def syndrome(word26):
    """Remainder of a 26-bit block divided by the RDS polynomial."""
    r = word26
    for i in range(25, 9, -1):
        if r >> i & 1:
            r ^= POLY << (i - 10)
    return r


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, name='RDS text decoder', in_sig=[np.uint8], out_sig=None)
        self.window = 0                   # last 104 bits, newest bit at the right
        self.nbits = 0
        self.ps = [' '] * 8
        self.rt = [' '] * 64
        self.last_print = ''

    def work(self, input_items, output_items):
        for b in input_items[0]:
            self.window = ((self.window << 1) | int(b & 1)) & ((1 << 104) - 1)
            self.nbits += 1
            if self.nbits >= 104:
                self.check_group()
        return len(input_items[0])

    def check_group(self):
        blocks = [(self.window >> (26 * (3 - k))) & 0x3FFFFFF for k in range(4)]
        names = [OFFSETS.get(syndrome(w)) for w in blocks]
        if names != ['A', 'B', 'C', 'D']:
            return
        a, b, c, d = [w >> 10 for w in blocks]   # keep the 16 data bits
        group_type, version = b >> 12, (b >> 11) & 1
        if group_type == 0:                       # station name
            i = b & 3
            self.ps[2 * i:2 * i + 2] = [chr(d >> 8), chr(d & 0xFF)]
        elif group_type == 2 and version == 0:    # RadioText
            i = b & 15
            self.rt[4 * i:4 * i + 4] = [chr(c >> 8), chr(c & 0xFF), chr(d >> 8), chr(d & 0xFF)]
        text = 'PS: [%s]   RT: [%s]' % (''.join(self.ps), ''.join(self.rt).split('\r')[0].rstrip())
        if text != self.last_print:
            print(text, flush=True)
            self.last_print = text
