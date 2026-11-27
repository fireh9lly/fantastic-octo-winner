# Third-party notices

MoonletOS (like amuletOS before it) bundles the following code. Both are compiled into the Games screen (`game/device/gbprobe.c`).

## Peanut-GB

`game/third_party/peanut_gb/peanut_gb.h`, https://github.com/deltabeard/Peanut-GB

MIT License. Copyright (c) 2018-2023 Mahyar Koshkouei. Parts are taken from SameBoy
(https://github.com/LIJI32/SameBoy), Copyright (c) 2015-2019 Lior Halphon, MIT License. The full license text is
at the top of `peanut_gb.h`.

## minigb_apu

`game/third_party/minigb_apu/`, from the Peanut-GB examples (https://github.com/deltabeard/Peanut-GB)

MIT License. Copyright (c) 2017 Alex Baines, Copyright (c) 2019 Mahyar Koshkouei. The full license text is in
`game/third_party/minigb_apu/LICENSE`.

## The MIT License text (as used by both)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Inter

`art/fonts/Inter-Bold.otf`, https://github.com/rsms/inter, Copyright 2016-2023 The Inter Project Authors, SIL Open
Font License 1.1 (full text: `art/fonts/OFL.txt`). Used by `art/orange.py` to draw the menu labels into the
firmware's images; the font file itself is not put in the firmware.
