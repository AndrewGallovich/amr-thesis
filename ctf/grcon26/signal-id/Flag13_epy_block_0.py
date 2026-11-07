import numpy as np
from gnuradio import gr

PREAMBLE = 0xAB   # sent 16 times before every alert header: 10101011


class Reader:
    """Reads bytes (8 bits, smallest bit first) once it has found the preamble."""
    def __init__(self, invert):
        self.invert = invert
        self.reg = 0          # last 16 bits
        self.locked = False
        self.byte = 0
        self.nbits = 0
        self.text = ''

    def push(self, bit):
        bit ^= self.invert
        if not self.locked:
            # Step 2: look for two preamble bytes in a row (bits arrive smallest-first)
            self.reg = ((self.reg >> 1) | (bit << 15)) & 0xFFFF
            if self.reg == (PREAMBLE << 8) | PREAMBLE:
                self.locked, self.byte, self.nbits, self.text = True, 0, 0, ''
            return None
        # Step 3: build bytes, smallest bit first
        self.byte |= bit << self.nbits
        self.nbits += 1
        if self.nbits < 8:
            return None
        b, self.byte, self.nbits = self.byte, 0, 0
        if b == PREAMBLE and not self.text:
            return None                      # still in the preamble
        if 32 <= b < 127:
            self.text += chr(b)
            return None
        # a non-text byte = end of this header
        self.locked, self.reg = False, 0
        return self.text if len(self.text) >= 4 else None


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='Weather alert (SAME) decoder',
            in_sig=[np.uint8],   # one 0/1 per bit (520.83 bits/s), from the Binary Slicer
            out_sig=None
        )
        # we don't know which tone the slicer calls 1, so read both ways
        self.readers = [Reader(0), Reader(1)]
        self.counts = {}      # how many times each header has been read

    def work(self, input_items, output_items):
        for b in input_items[0]:
            for r in self.readers:
                msg = r.push(int(b))
                if msg:
                    # Step 4: headers repeat, so only trust one we've read twice identically
                    self.counts[msg] = self.counts.get(msg, 0) + 1
                    if self.counts[msg] == 2:
                        print(f"Alert: {msg}", flush=True)
        return len(input_items[0])