import numpy as np
from gnuradio import gr


def crc_x25(data):
    """Packet radio's error check (CRC-16). Same idea as the RDS check bits."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


def callsign(addr7):
    """Each address is 6 letters shifted left by 1 bit, plus 1 byte for the number."""
    name = ''.join(chr(b >> 1) for b in addr7[:6]).strip()
    ssid = (addr7[6] >> 1) & 0x0F
    return f"{name}-{ssid}" if ssid else name


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='Packet radio decoder',
            in_sig=[np.uint8],   # one 0/1 per bit, from the Binary Slicer
            out_sig=None         # prints to the console
        )
        self.prev_level = 0      # beep level of the previous bit
        self.ones = 0            # how many 1 bits in a row
        self.in_frame = False    # between two flags?
        self.bits = []           # bits of the current message

    # Step 1: "did the beep change?"  changed = 0, stayed = 1
    def work(self, input_items, output_items):
        for level in input_items[0]:
            bit = 1 if level == self.prev_level else 0
            self.prev_level = level
            self.push_bit(bit)
        return len(input_items[0])

    # Step 2: find the start/end markers and remove filler bits
    def push_bit(self, bit):
        if bit == 1:
            self.ones += 1
            if self.ones > 6:                    # 7+ ones in a row: garbage, reset
                self.in_frame = False
                self.bits = []
            elif self.in_frame:
                self.bits.append(1)
            return

        if self.ones == 6:                       # 01111110 = start/end marker ("flag")
            if self.in_frame:
                self.bits = self.bits[:-6]       # drop the marker's own 1s
                self.end_frame()
            self.in_frame = True
            self.bits = []
        elif self.ones == 5:                     # filler 0 after five 1s: skip it
            pass
        elif self.in_frame:
            self.bits.append(0)
        self.ones = 0

    # Step 3: bits -> bytes, check for errors, print the message
    def end_frame(self):
        n = len(self.bits) // 8
        if n < 18:                               # too short to be a real message
            return
        data = bytes(sum(self.bits[i*8 + k] << k for k in range(8)) for i in range(n))
        body, fcs = data[:-2], data[-2] | (data[-1] << 8)
        if crc_x25(body) != fcs:                 # failed the error check
            return

        dest = callsign(body[0:7])
        src = callsign(body[7:14])
        i = 14
        while not body[i - 1] & 1:               # skip any relay stations
            i += 7
        info = body[i + 2:]                      # skip 2 control bytes
        text = info.decode('ascii', errors='replace')
        print(f"{src} > {dest}: {text}", flush=True)