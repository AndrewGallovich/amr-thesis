import numpy as np
from gnuradio import gr

MORSE = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5', '-....': '6',
    '--...': '7', '---..': '8', '----.': '9',
    '-.--.': '(', '-.--.-': ')', '..--.-': '_', '-...-': '=',
}

class blk(gr.sync_block):
    def __init__(self, samp_rate=10000, threshold=0.006, unit_ms=65):
        gr.sync_block.__init__(
            self,
            name='Morse decoder',
            in_sig=[np.float32],
            out_sig=None
        )
        self.samp_rate = samp_rate
        self.threshold = threshold
        self.unit_ms = unit_ms
        self.state = False
        self.count = 0
        self.letter = ''   # dots and dashes collected so far

    def finish_letter(self):
        if self.letter:
            print(MORSE.get(self.letter, '?'), end='', flush=True)
            self.letter = ''

    def work(self, input_items, output_items):
        for x in input_items[0]:
            on = x > self.threshold
            if on == self.state:
                self.count += 1
                continue

            # State flipped: measure the stretch that just ended, in units
            units = self.count / self.samp_rate * 1000 / self.unit_ms

            if self.state:                       # an ON just ended
                self.letter += '.' if units < 2 else '-'
            else:                                # an OFF just ended
                if units >= 5:                   # word gap
                    self.finish_letter()
                    print(' ', end='', flush=True)
                elif units >= 2:                 # letter gap
                    self.finish_letter()
                # under 2 units: gap inside a letter, do nothing

            self.state = on
            self.count = 1
        return len(input_items[0])