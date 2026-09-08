# Autonomous learning log

## Run cycle 1 - mobile playability in the first viewport

- Champion before cycle: `c7a1b192d613b316bdb59bc50fac4238091cac52` as the technically green branch head under review.
- Observation: at 390x844 the full page was 390x967 and touch controls were pushed below a large empty game-container area.
- Confirmed cause: the canvas scaled down on narrow screens while `#game` kept the desktop `min-height: 540px`.
- Hypothesis: remove the desktop minimum height only on narrow screens so the touch controls follow the real canvas and stay in the first viewport.
- RED evidence: `588dc611b70e9d16e81571978b60bbf719aa11e9` measured document height 967px against an 844px viewport.
- Implementation: `ae719563b70c721d338ba19007edd471cd550d81` added the narrow-screen `#game { min-height: 0; }` override.
- Result: document height fell to 852px and the complete touch-control block became visible inside the 844px viewport.
- Test refinement: `9e8d27405fa3c4aa3a24ac86c4d1930cdb38a31f` replaced the proxy metric of zero page scroll with the product invariant that the entire touch-control block is reachable in the first viewport and that touch input actually moves the player.
- Verification: all five mandatory repository gates succeeded on `9e8d27405fa3c4aa3a24ac86c4d1930cdb38a31f`; final browser evidence visually confirms the controls are reachable.
- Decision: ACCEPT.
- Confirmed lesson: browser screenshots can expose a real usability failure that a green interaction test misses.
- Incorrect assumption: total document height must be no greater than viewport height. The remaining 8px outer page overflow had no effect on control reachability.
- Do not repeat without new evidence: changing production layout only to remove harmless outer scroll after the actual control-reachability invariant is satisfied.
- Next main question: can Stream Slice keep canonical location IDs internally while presenting the same Russian location names already used by normal mode?
