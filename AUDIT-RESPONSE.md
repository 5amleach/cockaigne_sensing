# Response to AUDIT-2026-10

5 October 2026, Claude Code. One line per finding. "Fixed now" means in the commits of this date, with a test where one applies; "scheduled December" means before the January install, mostly alongside the live launcher; "by design" gives the reason in the line. The audit's three sharpest reproductions (the crashing pool, the blind climb, the 12.25 lean) were re-run here and confirmed before anything was changed.

## The five things to fix first

- **1 Launcher and supervision** — scheduled December: the live camera-to-bus launcher, process supervision and boot arrangement are the next build; fixed now within it, Resolume's REST is retried at start-up instead of ending the controller.
- **2 Camera and message health, blind fallback** — fixed now for the controller: freshness is the crowd message's own clock, the blind descent starts from the displayed position, and no bus message can kill the reader; per-camera health logging is scheduled December with the launcher.
- **3 Decision means displayed, validate every move** — fixed now: displayed advances only on a confirmed fire, unconfirmed decisions are published as such and retried from reality, and the validator demands every move the controller can ask for, including Barren probes and ring-preserving laterals, with no hard-coded ring count.
- **4 Delivery and reader robustness** — fixed now on the reader side (catch-all, field validation, reconnect); bounded bus delivery, per-client loss counts and a last-state snapshot for late joiners are scheduled December.
- **5 Truthful measurements and rehearsal** — fixed now: same-camera merging by pixel overlap, no ghost revival, calibration scaled by its stored image size, the fake day repaired, the lean capped and warmed up; validating calibration against tape-measured positions at the final camera height is December, on site.

## Documentation disagreements D1–D16

- **D1 four cameras** — fixed now: GUIDE says one source at a time and that the launcher is not built.
- **D2 old cohesion formula** — fixed now: ARCHITECTURE describes coordination, the blend and the ceiling.
- **D3 arousal inputs** — fixed now in ARCHITECTURE; speed-only arousal stays by design until there is footage from the final camera height to tune against.
- **D4 frame boundary** — fixed now: the rule is restated as it was meant (detect needs whole frames; nothing past detect gets one except actions' crops; bench snapshots are desk-only); the code was never the breach, the sentence was.
- **D5 thresholds in code** — fixed now: gate, bucket, margin, same-camera overlap, detector forgetting, capture retry and REST timeouts moved into config, and the claim softened to thresholds meant for on-site tuning.
- **D6 actions described as running** — fixed now: ARCHITECTURE marks the section as design, not implementation.
- **D7 arm audio** — fixed now in GUIDE: the stub sets one bank's volumes by ring; stems by arm and the crossfade are December.
- **D8 holding leaves the ring** — fixed now in code: holding uses loop clips or ring-preserving laterals, validated at start-up, with a test.
- **D9 "receive everything"** — fixed now in GUIDE: live-only delivery, no replay, failed sends dropped; replay and a joiner snapshot are December.
- **D10 reconnection conditional** — fixed now: the reader survives any message, validates crowd fields as finite numbers, and the start-up layout read retries.
- **D11 "never crashes" false** — fixed now: OSC sends are wrapped, return success, and the whole fire path is exception-free, with tests for a dead socket.
- **D12 id contract vs fake day** — fixed now: day() ends every lifetime and separates id blocks; the contract states the tracker's best-effort honestly.
- **D13 replay clocks** — fixed now in CONTRACTS: replay does not share one timeline with the controller's clock, and a decision's t is its planning time.
- **D14 bus record misses client traffic** — fixed now in CONTRACTS as a stated limit; recording the return traffic at the bus is December.
- **D15 reservoir "never resets"** — fixed now in GUIDE: never reset while running, empty after a restart — which stays by design, because after a crash the honest level is unknown and re-earning the ring is safer than restoring a guess.
- **D16 "the wall freezes"** — fixed now in GUIDE and RUNBOOK: what shows after a controller death is Resolume's composition behaviour, which this repository cannot promise.

## The catalogue, 1–37

1. Camera reopen logging — password now hidden in the open error (fixed now); per-attempt health logging is December, in the launcher.
2. Stale frames with fresh timestamps — scheduled December; needs the real camera to test against.
3. Detection omissions without health counts — scheduled December.
4. Missing calibration becomes an empty room — fixed now: an uncalibrated or unknown camera is skipped with a warning at most every thirty seconds.
5. Wrong-resolution calibration — fixed now: image_size is honoured, pixels scale, an aspect mismatch skips the camera with a warning, with a test.
6. Filter diagnostic counts — scheduled December.
7. Two nearby people merged — fixed now: same-camera sightings merge only on heavy pixel overlap, with a test for the audit's 20 cm case.
8. Identity swaps under crossing — by design for this version: the plain tracker is the logged choice (no Kalman); carrying confidence and observation age into Contract 1 is December.
9. Ghost revival with an old age — fixed now: expiry runs before matching, with the audit's one-hour test.
10. Bucket ordering and timed flushing — scheduled December; the live launcher owns the clock that must drive it.
11. Slow or backward input distorting scores — by design within the one-second dt clamp; an input-rate warning is December.
12. Mood labels without uncertainty — by design: the labels are a mechanical, provisional interpretation (logged 5 October) to be tuned on site; an unknown state is worth considering then.
13. Missing actions indistinguishable from inaction — by design until actions is built (December); zeros are the documented placeholder.
14. Unbounded action lean — fixed now: lean capped at half a draw, rates capped at five, treated as normal until 600 s of history, decaying on the controller's clock, with tests.
15. Received is not current — fixed now: freshness requires the message's own clock to advance, with a test.
16. Non-finite values — fixed now at the controller's intake (finite-number validation); sensing-side validation is December.
17. Bus loses messages without a count — scheduled December.
18. A slow listener delays everyone — scheduled December.
19. Reader dies on a malformed message — fixed now: logged and ignored, nothing kills the reader.
20. Lost decisions never retried — by design: the next decision supersedes within a minute, and a queue of stale fires would be worse; the warning now names the clip.
21. Bus record and ledger omit client traffic — scheduled December; stated plainly in CONTRACTS meanwhile.
22. Confirmation checks the slot, not the content — by design at this stage: content checks need the real composition; REST-error semantics are now explicit (counts as shown, logged) and the decision carries confirmed true/false.
23. Layout ignores the video layer — fixed now: the clip map is built from the configured video layer only; a duplicate-name warning is December.
24. Validator permits runtime gaps — fixed now: Barren probes, top-ring loops, ring-preserving routes and collapses are all required, no ring count hard-coded, with tests including the audit's crashing pool.
25. Planned state treated as displayed — fixed now: displayed advances only on confirmation, with a test.
26. Rewards from missing or unsuccessful experience — fixed now: settled at the next fire so the whole clip counts, only confirmed clips earn one, day change clears the pending reward; a never-opened window staying silent is by design (no evidence, no update).
27. The fake day inconsistent — fixed now: finite lifetimes, per-scenario id blocks, true duration, with a test.
28. Recorder buffering and appending — flush per line fixed now; appending across runs stays by design for a development tool, stated in its docstring.
29. Ledger durability — by design for one machine (single-line appends, flushed); locking and fsync are December if the soak test demands them.
30. Log rotation and disk policy — scheduled December.
31. Bus ends silently or spins — fixed now: a completion line, and an empty looped file stops instead of spinning.
32. Bench overcounts — fixed now: snapshot saves are checked and the floor summary counts its final flush.
33. Auto-calibration accepts poor fits — scheduled December, where tools.calibrate from measured markers supersedes it before install.
34. Permissive defaults mixed with crashes — scheduled December (configuration and message schema checks).
35. pool.json and weights not supplied — scheduled December with provisioning; the RUNBOOK now says pool.json must be generated first.
36. websockets floor too low — fixed now: >=13, and requirements.lock records the exact passing environment.
37. Clock slip unmeasured — late fires over one second are now logged; a strict timing bound on the fire path is December.

The remaining evidence gaps the audit names — mood thresholds, fit weights, claimed calibration accuracy, the real Resolume response shapes — are gaps, agreed; they close on site with the mounted cameras, the measured markers and the actual composition, and nothing in the repository should claim otherwise meanwhile.
