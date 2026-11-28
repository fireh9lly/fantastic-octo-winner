# On-device test: the key test (build 15)

What it is for: the wheel plans (PLAN.md, "Hold a button to change what the wheel does") need three facts that only
the player can give. Does stock send an event when a button is let go? Does it deliver wheel turns while Select or
Start is held, or keep them until the button is released? Is the wheel click the separate GPIO key?

**Build:** `./build.sh ~/Downloads/HIFIYF23.IMG BUILD_DIR 2620281115000000` (stamp 28 Nov, build 15: higher than
build 14, which is installed). Everything from build 14 is still in it; the new parts are the key test, the USB
name and the Settings row.

## Open it

- [ ] Settings: the row that said **Language** now says **Key Test**. Open it with A.
- [ ] A screen titled "Key Test" with "hold B: back" in the header, and these lines:
  1. `Held: nothing   ADC 1023` (the face button held now, and the raw button reading)
  2. `Click key: up`
  3. `Wheel events 0, 0 while held`
  4. `Wheel waiting: -0 +0`
  5. to 8. the last four button events, newest on top: milliseconds since the one before, the event in hex, its
     type (press, repeat, hold, or "type" plus a number for anything else) and the keys in it.

## Face buttons

- [ ] Press and release each button once: Up, Down, Left, Right, A, B (once only: three quick B presses leave),
      Select, Start. "Held" shows its name while it is down.
- [ ] Note what appears in the event lines **when you let go**. A new line with a type other than press = a release
      event (photo, please).
- [ ] Hold Up for 2 seconds: repeats, and a "hold" line?

## Wheel

- [ ] Turn the wheel a few notches each way with no button held: "Wheel events" counts up, the lines say Wheel- or
      Wheel+. The volume should not change on this screen.
- [ ] Press the wheel in (click): "Click key: pressed" while it is down? Any event line for it ("Click")?

## Wheel with a button held (the important one)

- [ ] Hold **Select**. While holding it, turn the wheel 3 notches, wait 2 seconds, then let go of Select.
      Watch "while held" and "Wheel waiting" during the hold, and the event lines just after you let go
      (photo of the screen right after letting go, please).
- [ ] The same with **Start**.

## Leave

- [ ] Hold B: back to the Settings list. Open Key Test again, press B three times quickly: back again.
- [ ] Settings › Game still opens the Games screen; Games and a Game Boy game still work.
- [ ] File transfer on the laptop: the disk now shows as **MOONLET OS AP30** (the name change since build 14).
