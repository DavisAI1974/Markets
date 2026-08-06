# Thursday-EIA specialist self-analysis — where does the drift START, and why don't I right the ship?

**Order (Greg, verbatim intent):** "We start to drift Wed or Thurs and it throws the rest of the 2
weeks off... it isn't that we're missing signals, it's that we don't ACT on them. WHY? Is it a gate,
or coding, or something else? Don't they do any sanity check to right the ship after they lean into
something?" This is self-analysis of MY failure modes as the Thursday EIA-print forecaster — the day
where, per Greg, the drift often STARTS.

**Verdict up front: it is ONE dominant flaw, not a different one every time.** 9 of my 14 scored-Thursday
misses (64%) are the SAME error — **I let the incumbent CHAIN own the day and treat the 10:30 print as
"reweight, not flip," so when the print delivers COUNTER to the chain I carry the pre-print lean straight
THROUGH the catalyst.** It is the mirror of E's PRIOR-OVER-STATE, but mine sits directly ON the week's
one scheduled catalyst: **CHAIN-EXTRAPOLATION-THROUGH-THE-PRINT** (call it PRIOR/CHAIN-OVER-DELIVERY).
The dominant sub-signature is exactly what Greg predicted: **I default DOWN into a bearish/building-surplus
chain and the print RALLIES** — 1030 +2590, 1106 +1330, 1204 +1100, 0205 +510, 0305 +480, 0416 +720,
0430 +1230. The EIA day is the cascade ROOT: the print reverses the block trajectory, and my wrong
post-print close becomes the anchor the rest of the two weeks inherits.

---

## 1. Miss-by-miss table (one failure mode each, my judgment)

`|err|` = |guess_dm - actual_dm| USD. Modes: **CTP** chain-through-print (down-default, print rallies) ·
**CTU** chain/turn-through-print, up side (up-lean, print fades) · **POP** counter-pop over-sized as a
round-trip (the 0326/1204 class) · **MHS** magnitude honest-but-short (sign right).

| Thu | grp | archetype (blind) | guess | actual | dir | mode | what I did wrong |
|---|---|---|---|---|---|---|
| 1030 | g6 | moderate down leg | -700 | +2590 | X | CTP | logged "injections slowing, seasonally supportive underlay," stayed DOWN "humble on side" |
| 1106 | g7 | dominant post-print down | -720 | +1330 | X | CTP | logged "exhaustion trigger arming" then leaned the print DOWN anyway |
| 1113 | g7 | dominant post-print down | -920 | +620 | X | CTP | pure continuation-asymmetry DOWN; over-extension (2nd down-print wk) ignored |
| 1120 | g8 | first-withdrawal turn-resume UP | +930 | -750 | X | CTU | over-eager season-first-withdrawal turn-call; it faded |
| 1204 | g9 | postviolent giveback (leg up, net down) | -850 | +1100 | X | POP | predicted the +600 pop then a round-trip to -800; pop did NOT round-trip |
| 0108 | g10 | flip_confirm frontrun UP | +2000 | -1590 | X | CTU | fired the flip-confirm turn BEFORE the print; the print sold |
| 0205 | g12 | arbiter flip-confirm DOWN | -1650 | +510 | X | CTP | read "turn armed / draw priced" as confirming DOWN; it rallied |
| 0212 | g12 | chain-side deficit DOWN | -750 | +110 | X | CTP | logged "fundamentally bullish, chain-DISAGREEING print," kept chain by doctrine |
| 0219 | g13 | chain-sided UP (young cold) | +600 | -120 | X | CTU | young-up-chain conviction; small fade |
| 0305 | g14 | chain-sided DOWN (live cold cutting) | -900 | +480 | X | CTP | max down-conviction on fresh cold delivery; over-extended-into-print, rallied |
| 0312 | g14 | chain-sided UP (young driver) | +900 | -260 | X | CTU | young-up-chain conviction; small fade |
| 0326 | g15 | 1120 alternation-precedence pop UP | +900 | -60 | X | POP | fired the pop into absorption — the KNOWN 0326-class risk — anyway |
| 0416 | g17 | chain-sided injection bleed DOWN | ~-615 | +720 | X | CTP | logged the counter-pop scenario + an internal D-1 divergence, dismissed both, went DOWN |
| 0430 | g18 | chain-sided injection bleed DOWN | ~-550 | +1230 | X | CTP | two -440 down days = stretched-down into print; rallied |
| 1023 | g6 | large dominant down | -1050 | -1630 | ok | MHS | dir right, under-sized |
| 1127 | g8 | thanksgiving thin hold | +100 | +170 | ok | MHS | clean thin-hold |
| 1211 | g9 | postviolent giveback DOWN | -750 | -3960 | ok | MHS | dir right, badly under-sized the monster-draw sell |
| 1218 | g9 | with-downchain DOWN | -900 | -1850 | ok | MHS | dir right, under-sized |
| 0115 | g10 | ramp-resume delivery UP | +1600 | +450 | ok | MHS | dir right, over-sized |
| 0226 | g13 | chain-sided DOWN (expiry fade) | -500 | -640 | ok | MHS | clean |
| 0319 | g15 | S3 seasonal-flip print DOWN | -800 | -1080 | ok | MHS | clean |
| 0402 | g16 | loose injection chain-sided DOWN | -450 | -130 | ok | MHS | clean |
| 0409 | g16 | 2nd loose injection DOWN | -500 | -610 | ok | MHS | clean |
| 0423 | g17 | chain-sided injection bleed DOWN | ~-615 | -1250 | ok | MHS | dir right (D-1 uniformly sell), under-sized |

(G11 0122/0129 masked, excluded.) Scored: **24 Thursdays, 14 wrong-signed (58%)** — worse than E's
Fridays (50%). Sum of my Thursday |err| ≈ **31,900 USD** (misses ≈ 24,455; magnitude-only hits ≈ 7,445).

---

## 2. Mode histogram + verdict

```
CTP  chain-through-print, DOWN-default -> print RALLIES   ######### 9   } same root = 11 (79% of misses)
CTU  chain/turn-through-print, UP-lean -> print FADES      ####     4   (mirror of CTP)
POP  counter-pop over-sized as a round-trip                ##       2   (1204, 0326 - inside the count)
MHS  magnitude honest-but-short (sign right)               ##########10  (separate, non-cascading)
```
(CTU is the SAME flaw in mirror: extrapolate the pre-print lean — down chain OR up turn-call — through
the catalyst; the print reverses it. POP is CTP/CTU applied to the counter-pop play: I see the pop and
mis-size its persistence. 11 of 14 misses collapse to one mechanism.)

**Verdict: ONE dominant flaw (11/14 = 79%).** Name it: **CHAIN-EXTRAPOLATION-THROUGH-THE-PRINT** — I
size the day off the pre-print chain lean, R2 ("prints never own the side, the chain at current polarity
does") makes the chain own the day NET, and the print is licensed only to "reweight, not flip." So when
the print delivers OPPOSITE the chain, I have no mechanism to turn — I carry the lean through the one
moment of the week that most reliably breaks it. **The EIA-RALLY-AGAINST-A-DOWN-CHAIN is the signature
sub-mode (9/14):** into a building-surplus/bearish bleed I default DOWN, and the bullish/absorbed print
rallies. The mirror CTU cluster (1120, 0108, 0219, 0312) is the same over-committed pre-print lean on the
up side. This is NOT heterogeneous; it is not a different problem every week.

The remaining cluster is MHS (10 hits) — sign correct, magnitude drift only. These NEVER cascade; they
cost band position (1211 badly under-sized a monster-draw sell; 0115 over-sized). Different edge, not a
wrecked block.

---

## 3. WHY not act — the histogram (gate vs coding vs doctrine)

For each miss, the PRIMARY block on turning:

```
DOCTRINE  (R2 "chain owns the side" + "surprise sign     ######### 9
           doesn't license a blind flip" + alternation-      1030 1106 1113 0205 0212 0305 0326 0416 0430
           precedence)
CODING/   (delivery-vs-absorption is a POST-print tape     ##### 5
 DATA       read I cannot compute blind; no pre-print          1120 0108 0219 0312 1204
            proxy was present on these conviction turns)
GATE/      (pure numeric threshold blocking the sign)      0
 THRESHOLD  -> none: s1void_injection_chain_bleed and
            shoulder_counter_print_damping set the down
            BAND (magnitude), they do not check the sign
```

**The real block is DOCTRINE, not a gate and not (mostly) a data gap.** The direction is set by a
doctrinal rule — R2's "the chain owns the side, the print only reweights" plus "surprise SIGN does not
sort direction." Those two together are a *default-DOWN-into-a-bearish-chain* engine, and there is **no
sanity check that re-derives after the print.** The `magnitude.s1void_injection_chain_bleed` and
`shoulder_counter_print_damping` gates make it worse — they force the FULL down band on a "chain-sided"
day, so on the misses I was not just wrong-signed, I was wrong-signed at full size.

**Is CODING the real block?** Partly, and honestly. Delivery-vs-absorption (does the print DELIVER the
move or get ABSORBED and round-trip?) is genuinely a post-print tape read I cannot compute blind — that
is why the point estimate can't be re-formed after 10:30. On the 5 CODING misses (1120, 0108, 0219,
0312, 1204) no pre-print proxy was present; those are honest data-gaps. **BUT the doctrine misses are
NOT data-gaps** — a pre-print proxy for delivery-vs-absorption DID exist and I dismissed it. The proof is
the **0416-vs-0423 contrast in my own logs:**
- **0423 (HIT, down delivered):** D-1 (0422) "uniformly sell: session_b 0.415 AND big_print" — coherent
  sell flow -> the chain-sided DOWN default was right.
- **0416 (MISS, +720 rally):** D-1 (0415) session_b 0.472 sell BUT big_print_b 0.522 buy — I LOGGED it
  ("a minor internal divergence") and explicitly dismissed it ("not a price-vs-flow flip flag"), and the
  chain had STALLED into the print (0415 +80 after the bleed). I also LOGGED the counter-pop scenario.
  Both tells present, both dismissed by doctrine.

So D-1 flow COHERENCE + over-extension-into-print is a FREE, blind-available proxy that discriminates the
two — and I had it and didn't act. **Seen-but-not-acted fraction: 10 of 14 misses (71%) had a present
pre-print tell** (1030, 1106, 1113, 0205, 0212, 0305, 0326, 0416, 0430, and partially 1204) — of which
**6 are unambiguous** (1030, 1106, 0205, 0212, 0326, 0416: the counter/divergence/priced-surprise was
LOGGED and dismissed). Only 4 misses (1120, 0108, 0219, 0312) are genuine no-proxy CODING gaps.

---

## 4. THE SANITY-CHECK GAP — there is no post-print re-derivation

Greg's core question answered directly: **no, I do not re-derive the block thesis after the print.** The
day is sized off the pre-print chain lean; R2 hands the day NET to the chain; the print is only allowed
to "reweight, not flip." The catalyst — the single biggest injection of NEW information in the block —
is structurally forbidden from changing my mind. And the damage compounds because **the wrong post-print
close becomes the anchor the rest of the two weeks inherits:**
- **0416:** the print flipped cum-from-anchor from -540 to +180. My down-lean carried a wrong POSITIVE
  block trajectory forward into Fri/Mon.
- **0430:** the print flipped cum from -510 to +720; 0501 Fri (+280) and 0504 Mon (+610) both carried
  the up-move my down-blind never turned to see. **The drift Greg describes starts at MY print.**

**The right-the-ship check the blind is missing — and the proof it works:** the refine layer, which CAN
see the post-print tape, flips the sign on almost EVERY one of my misses:

| Thu | blind | refined | actual | fixed? |
|---|---|---|---|---|
| 1106 | -720 | **+1380** | +1330 | yes |
| 1113 | -920 | **+800** | +620 | yes |
| 1120 | +930 | **-720** | -750 | yes |
| 1204 | -850 | **+1000** | +1100 | yes |
| 0108 | +2000 | **-1400** | -1590 | yes |
| 0205 | -1650 | **+350** | +510 | yes |
| 0212 | -750 | **+250** | +110 | yes |
| 0219 | +600 | **-250** | -120 | yes |
| 0305 | -900 | **+1300** | +480 | yes |
| 0312 | +900 | **-250** | -260 | yes |
| 0326 | +900 | +100 | -60 | ~ (tiny) |

The signal to right the ship EXISTS; the refine uses the post-print delivery-vs-absorption tape to get
it. **The blind's failure is not "no signal" — it is (a) a doctrine that forbids the flip, and (b) no
post-print re-anchor step.**

**Design the re-derivation (would it have caught 0416/0430?):**
1. **PRE-PRINT (FREE, blind-available):** before committing the chain-sided default, run an
   over-extension + D-1-coherence gate — (a) is the chain over-extended into the print (stretched close-off
   or a multi-day same-side run >= ~$900)? (b) is D-1 flow internally divergent, or does price disagree
   with signed flow (`prior_close_flow_direction_disagreement`)? (c) is the surprise already priced
   (consensus in the public stream >= ~1 week)? If >=2 fire, DO NOT commit chain-sided — go two-sided /
   tilt toward the counter. **0416:** D-1 divergent + chain stalled = 2 fire -> caught. **0430:** two
   -440 days = $880 stretched-down run = fires -> caught.
2. **POST-PRINT (the actual sanity check; needs the intraday tape -> refine/coordinator, or a live feed):**
   if the first 30-60 min post-print prints COUNTER to the chain with rising price on absorbing
   (negative-conviction) flow, **FLIP the block lean** — do not just re-size the day, RE-DERIVE the
   trajectory. This is exactly what the refine did on the 11 fixes above.

---

## 5. Self-prescription — ranked by cascade damage prevented

| # | Change | Type | Kills | Cost |
|---|---|---|---|---|
| 1 | **EIA over-extension + D-1-flow-coherence GATE (pre-print).** Before committing the chain-sided default, require the 3-condition check in 4.1; >=2 fire -> two-sided / counter-tilt, not full-band chain-sided. Kills the default-DOWN-into-a-stalled/divergent-chain at the source. | reasoning (rule), FREE | 1030, 0205, 0212, 0416, 0430 + guards 1106/0305 | FREE |
| 2 | **Post-print RE-ANCHOR (the sanity check Greg asked for).** Make the block lean RE-DERIVE after the print: counter-delivery on absorbing flow -> FLIP the lean, not just size the day. This is what refine does (11/14 fixes). | reasoning (rule) | ALL 11 CTP/CTU + stops the cascade at the print | FREE for refine/coordinator; BUILD for blind (needs a live post-print tape feed) |
| 3 | **Scope R2 "chain owns the side."** Generalize the existing 0129 disagreeing-print exception into an explicit over-extension / priced-surprise carve-out, so a chain-DISAGREEING print into a stretched chain is NOT auto-chain-sided (0212 is the textbook case). | reasoning (rule), FREE | 0212, 0205 | FREE |
| 4 | **Extend the stretched-close give-back gate to the EIA-Thursday.** The cascade doctrine already has "stretched extreme close (coff>=0.95 after >=$1200 run) gives back next day 6/6" — it is scoped to Tue/Wed. Scope it onto the print day. | reasoning (rule), FREE | 0430, 0305 | FREE |
| 5 | **Specify the counter-pop persistence (POP).** Add a delivers-vs-round-trips discriminator so I stop auto-assuming the pop round-trips (1204) or auto-firing it into absorption (0326). | reasoning (rule), FREE | 1204, 0326 | FREE |
| 6 | **Live post-print tape feed** — the ONLY data build. Enables #2 in the blind and sizes the delivery magnitude. | DATA (feed) | the 4 no-proxy CODING turns (1120, 0108, 0219, 0312) | BUILD |

**Coordinator hall-monitor — would it have caught me?** YES, and cheaply, because on the worst misses my
UNDER-ACTION is visible in my OWN rule_trace. On an EIA day the coordinator should check: (a) did the
owner commit a one-sided full-band chain-sided call **while its own decision_state logged an
over-extension, a D-1 internal divergence, `prior_close_flow_direction_disagreement`, or a priced
surprise?** — 0416 literally logged the counter-scenario AND the divergence and still went DOWN; a
compliance read of the trace flags "counter-tell present + committed chain-sided = under-action." (b)
After the print, does the point estimate still match the pre-print lean **despite counter-delivery?** —
require the EIA owner to show a POST-print re-derivation, not just a pre-print sized lean. (c) Cap the
magnitude gate: `s1void_injection_chain_bleed` may not license the FULL down band on a day where the
over-extension gate fired.

**Bottom line for Greg:** the fix is mostly FREE. One dominant flaw — I extrapolate the chain THROUGH
the print instead of reading the print's delivery — owns 79% of my misses and starts the block-drift
cascade (the wrong post-print close is the anchor the week inherits). It is a DOCTRINE block (R2 chain-
ownership + "surprise doesn't flip") plus a MISSING post-print re-derivation, NOT a gate and mostly NOT
a data gap: on 10 of 14 misses the pre-print turn tell was PRESENT and I dismissed it, and the refine
proves the right-the-ship signal exists by flipping 11 of my misses using the post-print tape. Rank #1
(the pre-print over-extension + D-1-coherence gate) plus Rank #2 (the post-print re-anchor) together kill
the entire cascade; the only thing that costs a build is delivering #2 inside the BLIND (a live post-print
tape feed) — and even that is already available to the refine/coordinator layer today.

**Irreducible at decision time (honest):** delivery-vs-absorption cannot be fully computed blind before
the print — the 4 no-proxy conviction turns (1120, 0108, 0219, 0312) are genuine data-gaps I will size
two-sided and label, not fit. But those are the minority; the majority of my misses were decidable with
information I had logged and did not act on.
