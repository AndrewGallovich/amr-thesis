import numpy as np
from gnuradio import gr

# ---------- M17 building blocks ----------
RAND = [0xD6,0xB5,0xE2,0x30,0x82,0xFF,0x84,0x62,0xBA,0x4E,0x96,0x90,0xD8,0x98,0xDD,0x5D,
        0x0C,0xC8,0x52,0x43,0x91,0x1D,0xF8,0x6E,0x68,0x2F,0x35,0xDA,0x14,0xEA,0xCD,0x76,
        0x19,0x8D,0xD5,0x80,0xD1,0x33,0x87,0x13,0x57,0x18,0x2D,0x29,0x78,0xC3]
RAND_BITS = [(RAND[i // 8] >> (7 - i % 8)) & 1 for i in range(368)]   # "scrambler" pattern
SHUFFLE = [(45 * i + 92 * i * i) % 368 for i in range(368)]           # interleaver order
P1 = [1] + [1, 0, 1, 1] * 15        # which coded bits were kept (setup frame)
P3 = [1, 1, 1, 1, 1, 1, 1, 0]       # which coded bits were kept (packet frames)
SYNC_LSF = [int(c) for c in '0101010111110111']   # 0x55F7: "setup frame next"
SYNC_PKT = [int(c) for c in '0111010111111111']   # 0x75FF: "packet frame next"


def unscramble(bits):
    bits = [b ^ r for b, r in zip(bits, RAND_BITS)]   # undo the scrambler
    out = [0] * 368
    for i in range(368):                              # undo the shuffle
        out[SHUFFLE[i]] = bits[i]
    return out


def fill_gaps(bits, pattern, total):
    """Put back the bits the sender dropped, as 'unknown' (None)."""
    out, k, i = [], 0, 0
    while len(out) < total:
        if pattern[i % len(pattern)]:
            out.append(bits[k] if k < len(bits) else None)
            k += 1
        else:
            out.append(None)
        i += 1
    return out


def viterbi(coded):
    """Undo the error-correcting code: find the input bits that best explain what we got."""
    def encode(state, b):
        r = (b << 4) | state
        g1 = ((r >> 4) ^ (r >> 1) ^ r) & 1
        g2 = ((r >> 4) ^ (r >> 3) ^ (r >> 2) ^ r) & 1
        return g1, g2, (r >> 1) & 0xF
    INF = 10 ** 9
    cost = [0] + [INF] * 15
    paths = [[] for _ in range(16)]
    for t in range(0, len(coded), 2):
        c1, c2 = coded[t], coded[t + 1]
        new_cost, new_paths = [INF] * 16, [None] * 16
        for s in range(16):
            if cost[s] >= INF:
                continue
            for b in (0, 1):
                g1, g2, ns = encode(s, b)
                c = cost[s] + (c1 is not None and c1 != g1) + (c2 is not None and c2 != g2)
                if c < new_cost[ns]:
                    new_cost[ns], new_paths[ns] = c, paths[s] + [b]
        cost, paths = new_cost, new_paths
    best = min(range(16), key=lambda s: cost[s])
    return paths[best], cost[best]


def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x5935) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def to_bytes(bits):
    return bytes(int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits) - 7, 8))


# ---------- the GNU Radio block ----------
class blk(gr.sync_block):
    def __init__(self, threshold=0.40):
        gr.sync_block.__init__(
            self,
            name='M17 packet decoder',
            in_sig=[np.float32],   # one value per symbol, from Symbol Sync
            out_sig=None
        )
        self.threshold = threshold   # between the inner and outer frequency levels
        self.bits = []               # recent bits, to spot the sync words
        self.mode = 'hunt'
        self.frame = []
        self.packet = b''
        self.last_printed = None

    def work(self, input_items, output_items):
        for x in input_items[0]:
            # Step 1: four frequency levels -> 2 bits each
            if x > self.threshold:
                pair = (0, 1)        # +3
            elif x > 0:
                pair = (0, 0)        # +1
            elif x > -self.threshold:
                pair = (1, 0)        # -1
            else:
                pair = (1, 1)        # -3
            for b in pair:
                self.push(b)
        return len(input_items[0])

    def push(self, b):
        if self.mode == 'hunt':
            # Step 2: look for a sync word
            self.bits = (self.bits + [b])[-16:]
            if self.bits == SYNC_LSF:
                self.mode, self.frame, self.packet = 'lsf', [], b''
            elif self.bits == SYNC_PKT:
                self.mode, self.frame = 'pkt', []
            return
        # Step 3: collect one frame (368 bits)
        self.frame.append(b)
        if len(self.frame) < 368:
            return
        frame, mode = self.frame, self.mode
        self.mode, self.bits = 'hunt', []
        if mode == 'lsf':
            return                   # setup frame: callsigns etc. (not needed for the text)
        # Step 4: unscramble, un-shuffle, refill dropped bits, undo error correction
        dec, errors = viterbi(fill_gaps(unscramble(frame), P3, 420))
        if errors > 20:
            self.packet = b''
            return
        data = to_bytes(dec[:200])               # 25 bytes of the message
        last = dec[200]                          # 1 = this is the last frame
        count = int(''.join(map(str, dec[201:206])), 2)
        if not last:
            self.packet += data
            return
        self.packet += data[:count]              # last frame: only 'count' bytes are real
        # Step 5: check the whole message, then print it
        msg, self.packet = self.packet, b''
        if len(msg) < 3 or crc16(msg[:-2]) != int.from_bytes(msg[-2:], 'big'):
            return
        text = msg[1:-2].rstrip(b'\x00').decode('ascii', errors='replace')   # byte 0 = message type
        if text != self.last_printed:
            print(f"M17 message (type {msg[0]}): {text}", flush=True)
            self.last_printed = text