# UI mock-ups

PC renders of the planned interface at the player's real 296×240, with colours rounded to RGB565 like the screen.
Nothing here runs on the player. The design is written up in [PLAN.md](../../PLAN.md#look-and-feel-decided-2026-11-27).

```sh
python3 art/mockups/overview.py        # writes docs/design/ui/*.png and docs/design/ui/overview.png
```

| File | What it draws |
|---|---|
| `shapes.py` | Building blocks: blobs, painted strokes, almond eyes, the first set of beings (arch, dome, star, ...). Its own main renders the paper-background round. |
| `black_orange.py` | Highlight bars with dots / lines / waves, the black-and-orange kit. |
| `forms.py` | The pet's five adult forms on the mood map, the two-headed sapling, the pet page. |
| `colourways.py` | The five colourways, the whaleian, the gallery, Settings › Look, the species picker, home and Now Playing with the pet. |
| `overview.py` | Renders the current set into `docs/design/ui/`. |

Each module builds on the one above it. Drawing happens at 4× and is scaled down for smooth edges.

Needs Pillow and numpy, plus these fonts at their Debian/Ubuntu paths (`fonts-inter`, `fonts-jetbrains-mono`,
`fonts-dejavu-core`): Inter Display (Black, ExtraBold, Bold, SemiBold, Medium), JetBrains Mono Bold, DejaVu Sans
Bold (sheet captions only). The fonts are stand-ins until we design our own.
