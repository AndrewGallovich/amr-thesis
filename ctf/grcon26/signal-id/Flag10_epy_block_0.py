import numpy as np
from gnuradio import gr

SYNC = 0x7CD215D8   # "a batch starts here" marker
IDLE = 0x7A89C197   # "nothing to send" filler
MASK = 0xFFFFFFFF
NUMERIC = '0123456789.U -)('   # pager digits (4 bits each)


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='Pager (POCSAG) decoder',
            in_sig=[np.uint8],   # one 0/1 per bit, from the Binary Slicer
            out_sig=None         # prints to the console
        )
        self.reg = 0             # last 32 bits, used to spot the marker
        self.synced = False      # inside a batch?
        self.invert = False      # 0s and 1s flipped?
        self.word = 0            # current 32-bit word being collected
        self.nbits = 0
        self.count = 0           # words read in this batch (16 per batch)
        self.addr = None         # who the current message is for
        self.func = 0
        self.msg_bits = []       # message bits collected so far

    def work(self, input_items, output_items):
        for b in input_items[0]:
            b = int(b)
            if not self.synced:
                # Step 1: look for the marker (or its flipped version)
                self.reg = ((self.reg << 1) | b) & MASK
                if self.reg in (SYNC, SYNC ^ MASK):
                    self.invert = self.reg != SYNC
                    self.start_batch()
                continue

            # Step 2: collect 32-bit words
            self.word = (self.word << 1) | (b ^ self.invert)
            self.nbits += 1
            if self.nbits < 32:
                continue
            word, self.word, self.nbits = self.word, 0, 0

            if self.count == 16:             # a batch is 16 words, then a new marker
                if word == SYNC:
                    self.count = 0
                else:                        # transmission ended
                    self.flush()
                    self.synced = False
                    self.reg = 0
                continue

            self.handle(word, self.count // 2)
            self.count += 1
        return len(input_items[0])

    def start_batch(self):
        self.synced = True
        self.word = 0
        self.nbits = 0
        self.count = 0

    # Step 3: each word is either an address, message data, or filler
    def handle(self, word, frame):
        if word == IDLE:
            self.flush()
        elif word >> 31 == 0:                # first bit 0 = address
            self.flush()
            self.addr = (((word >> 13) & 0x3FFFF) << 3) | frame
            self.func = (word >> 11) & 0x3
            self.msg_bits = []
        else:                                # first bit 1 = 20 bits of message
            data = (word >> 11) & 0xFFFFF
            self.msg_bits += [(data >> (19 - i)) & 1 for i in range(20)]

    # Step 4: message bits -> text (letters are 7 bits, digits 4 bits)
    def flush(self):
        if self.addr is None:
            return
        bits = self.msg_bits
        letters = ''.join(
            chr(sum(bits[i + k] << k for k in range(7)))
            for i in range(0, len(bits) - 6, 7))
        letters = ''.join(c for c in letters if 32 <= ord(c) < 127)
        digits = ''.join(
            NUMERIC[sum(bits[i + k] << k for k in range(4))]
            for i in range(0, len(bits) - 3, 4))
        print(f"Pager {self.addr} (type {self.func}):", flush=True)
        print(f"   as letters: {letters}", flush=True)
        print(f"   as digits:  {digits.strip()}", flush=True)
        self.addr = None
        self.msg_bits = []