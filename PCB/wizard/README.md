# Bring-up wizards

One step-by-step bench wizard per board: multimeter checks without power first, then the first power-up with a
current limit, then the board in the stack. Each page is a single standalone HTML file next to the design; open it
from a clone by double-clicking (no internet needed). Answers are kept in that browser, and the summary at the end
of each phase can be copied into a chat. The wizards are in Dutch, like the bench sessions they come from.

| Board | Wizard |
|---|---|
| Main board rev 0.6 | [`../rev0.6/main/WIZARD.html`](../rev0.6/main/WIZARD.html) |
| USB module rev 0.6 | [`../rev0.6/usb/WIZARD.html`](../rev0.6/usb/WIZARD.html) |
| GNSS module rev 0.4 (rev 0.6 set) | [`../rev0.4/gnss/WIZARD.html`](../rev0.4/gnss/WIZARD.html) |
| Audio module rev 0.4 (rev 0.6 set) | [`../rev0.4/audio/WIZARD.html`](../rev0.4/audio/WIZARD.html) |
| USB module rev 0.7 | [`../rev0.7/usb/WIZARD.html`](../rev0.7/usb/WIZARD.html) |
| Audio module rev 0.7 (with mic input) | [`../rev0.7/audio/WIZARD.html`](../rev0.7/audio/WIZARD.html) |
| Capture module rev 0.7, 1 camera | [`../rev0.7/capture_1cam/WIZARD.html`](../rev0.7/capture_1cam/WIZARD.html) |
| Capture module rev 0.7, 2 cameras | [`../rev0.7/capture_2cam/WIZARD.html`](../rev0.7/capture_2cam/WIZARD.html) |

## Where the values come from

- **Rev 0.6 set (main, USB, GNSS, audio 0.4):** the wizard used on the bench in October/November 2026, with the
  faults found on the first boards added to the relevant steps (U15 PowerPAD on the USB module, U13 rotated, U2 pin 4
  open, dead LEDs D10/D16, C34 short on the audio module). The main board gets a new "VIM3 en scherm" phase
  (ribbon continuity, VIM3 power, HDMI and panel).
- **Rev 0.7 boards:** derived from the pad nets in the `.kicad_pcb` files. Fixed resistive paths give exact values
  (75 ohm video termination, 33 ohm R212, 2.2k bias, 20k across the 5 V input of the audio module). Currents for the
  capture modules are estimates from the design notes; these steps say so and ask you to note the value.
  The rev 0.7 wizards have not been used on real boards yet.

## Editing

The step data lives in `boards/*.js`; `engine.html` is the shared page. After editing, rebuild all pages:

    python3 PCB/wizard/build.py

Each data file starts with `// out: <path under PCB/>` to say where its page goes. Steps are objects with
`t` (title), `setting`, `red` / `black` (probe points), `exp` (expected value), `small` (note), `pre` (text before
the measurement) and `fail` (what to do when it is off); `info: true` with `body` makes a text-only step.
