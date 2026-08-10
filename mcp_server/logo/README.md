# Markets Terminal - logo

**`markets_terminal_icon.svg` is the mark.** Candidate A, "Forward Curve", chosen S118. The three
candidates and the contact sheets are kept beside it as the record of the choice, not as
alternatives in play.

What it draws, left to right: the **anchor** (hollow - a level we start FROM, not one we called),
week one rising through a shallow give-back, **the weekend GAP**, week two, and the **print**. The
gap is the point. Drawing a line through untraded hours is the one thing this project's own render
rule forbids (`break_gaps`, S104/S105), so the mark carries the rule rather than a generic
up-and-to-the-right chart.

| file | what |
|---|---|
| `markets_terminal_icon.svg` / `.png` | the mark. SVG is the source; the PNG is a render of it |
| `markets_terminal_{a,b,c}_*.svg` | the three candidates, kept as the record |
| `logo_sheet_phone.svg` / `.png` | portrait contact sheet - each mark at 512, 64 and 32, light and dark |
| `logo_sheet.html` | desk contact sheet - adds 16px and circle-masked previews |
| `make_phone_sheet.py`, `make_logo_sheet.py` | generate the sheets from the SVGs |
| `rasterize.py` | regenerate every PNG from its SVG (`pip install cairosvg`) |

**Never hand-edit a PNG here.** They are renders; edit the SVG and re-run `rasterize.py`. Same
store-and-render discipline every other document in this repo follows.

Known limit, stated rather than discovered later: A carries the most detail of the three and is the
weakest at 32px and below. Accepted deliberately - if a host ever renders it that small and it
matters, the fix is a simplified small-size variant (drop the anchor line and hollow ring, thicken
the strokes), not a different logo.
