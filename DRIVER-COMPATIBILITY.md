# Driver compatibility: 472.12 and 580.97

This matrix tracks the local TITAN RTX (TU102, VBIOS 90.02.1E.00.02),
TITAN Xp (GP102, VBIOS 86.02.3D.00.01), and GTX 770 (GK104, VBIOS
80.04.c3.00.01, PCI 1184 / subsystem 1033196e) on Windows. Results are scoped to
these boards and drivers. Blackwell's existing 580.97 controls are separate;
this comparison does not establish a 472.12 Blackwell path. The 580.97 baseline
column describes the TITAN boards; GTX 770 was tested only on 472.12.

| Feature | 580.97 baseline | TITAN RTX on 472.12 | TITAN Xp on 472.12 | GTX 770 on 472.12 |
|---|---|---|---|---|
| NVML loading and GPU identity | Confirmed | Confirmed; Standard-driver NVSMI directory supported | Confirmed; selected by PCI slot | Confirmed; NVAPI/NVML agree on PCI identity |
| Core offset and range | Confirmed through NVML | Confirmed through NVAPI Pstates20 | Confirmed through NVAPI Pstates20 | Confirmed through NVAPI Pstates20; repeated load/restore cycles |
| Ordinary memory offset and range | Confirmed through NVML | Confirmed; same true-MHz slider units | Confirmed; same true-MHz slider units | Confirmed; +25 true MHz moved reported memory 3505 → 3557 MHz |
| Applied-offset and P0 maximum-clock telemetry | Confirmed through NVML | Confirmed through NVAPI Pstates20 | Confirmed through NVAPI Pstates20 | Confirmed through NVAPI Pstates20 |
| V/F point lock | Confirmed | Confirmed during loaded offset checks; exact lock restored | Confirmed during loaded offset checks; exact lock restored | Unavailable through the current V/F path |
| Fan duty, RPM, manual control and Auto | Confirmed | Both fan controls' requested levels and Auto policies verified through NVAPI; zero RPM is expected on this water-cooled card | Manual duty/RPM response and Auto verified through NVAPI cooler controls | Manual 50%, RPM response and exact Auto-policy restoration confirmed |
| Clock event/performance-limit reasons | Confirmed | Legacy NVML ThrottleReasons fallback implemented | Legacy NVML ThrottleReasons fallback implemented | NVAPI performance-decrease reasons readable |
| V/F curve editing and de-flatten planners | Confirmed | Negative-point write/reset and raised-cap de-flatten confirmed | Negative-point write/reset and raised-cap de-flatten confirmed; the regular ramp no longer treats the stock clock-list maximum as an overclock ceiling | Not applicable: editor, planners, point locks and shortcuts suppressed; switching back restores RTX’s 128 points |
| NVVDD rail offsets and all four limits | Confirmed; see voltage measurements below | Confirmed, including each live ceiling clamp and idle floor | Confirmed, including each live ceiling clamp; floor uses verified legacy re-send | Private layout unvalidated; controls blocked |
| Per-domain clock offsets | Confirmed for mapped controls | XBAR, Additional Memory Clock Offset, SYS, VIDEO and LTC each moved by about +30 MHz under load | Additional Memory Clock Offset +25 MHz moved reported memory by +20.25 MHz twice; other paired controls remain hidden | Unvalidated; private controls hidden, including Additional Memory Clock Offset |
| Power limit and voltage boost | Confirmed | Confirmed with independent readback | Confirmed with independent readback | NVML power-limit range and voltage-boost getter unavailable; sliders hidden |
| NVML frequency lock | Works on Turing; unsupported on Pascal | Confirmed at 1500 MHz under load; legacy RM readback also sees another process's range | Unsupported baseline; V/F point lock remains available | GPU 1176..1176 MHz and memory 3505..3505 MHz both return Not Supported (3), while elevated |
| Profiles, Undo, Reset all and Max it | Existing composite actions | All 13 UI callback checks passed; exact controls/table/lock restoration | All 13 UI callback checks passed; exact controls/table/lock restoration | Profiles omit the inapplicable V/F table; Reset all skips curve writes; Max it hidden. Core/memory/fan and I2C restoration verified separately; default profile replay covered by hardware-free tests |
| I2C regulator control | Board/tool dependent | MP2888A verified under load: +75 mV request moved rail-minus-VID by +45 mV; original raw value restored | No matching regulator found on this board | NCP4206 absolute target verified at 1250/1262.5 mV; Auto and profile restoration exact |
| Memory timing capture and writes | Board/tool dependent | Capture works; FAW 16→17 is dropped by hardware and reported as dropped | Capture, FAW 24→25 write, and exact restore confirmed | Capture and 15 delay fields verified; exact restoration; CL 18→19 triggered driver recovery (details below) |
| MSVDD | Unavailable on these TITAN boards | Unavailable; no confirmed rail | Unavailable; no confirmed rail | No confirmed rail |

Export presence or a successful write return alone is not a functional result. Manual targets
and Auto policies were verified and restored on both fan channels.
The [public validation summary](experiments/compatibility-validation-47212.json)
records the integrated checks and measured outcomes without private paths,
device UUIDs, or raw recovery buffers.

## Ordinary clock offsets

Driver 472.12 lacks both the modern NVML clock-offset API and its older
GpcClkVfOffset/MemClkVfOffset family. Druta reads the public NVAPI Pstates20
table and submits a sparse P0 request containing one clock delta and no voltage
or other-domain entries. The modern NVML path retains precedence when present.

NVAPI reports memory offsets in the reported memory clock's MHz. NVML doubles
those numbers. The backend converts between them so profiles, bounds, and
the true-memory-MHz slider retain their meaning across drivers.

| Card | Core range | Memory range in NVAPI MHz | Normalized NVML memory units | Memory slider range in true MHz |
|---|---:|---:|---:|---:|
| TITAN RTX | -1000..+1000 MHz | -1000..+3000 | -2000..+6000 | -250..+750 |
| TITAN Xp | -200..+1200 MHz | -1000..+1000 | -2000..+2000 | -250..+250 |
| GTX 770 | -105..+1001 MHz | -2695..+3505 | -5390..+7010 | -1347.5..+1752.5 |

The TITAN 472.12 checks held a 900 mV V/F point under a CUDA bandwidth workload
targeted by PCI slot. These are short functional measurements, with memory
requests subject to the card's clock quantization.

| Card | Request | Reported clock before → after | P0 maximum before → after |
|---|---|---|---|
| TITAN RTX | Core +15 MHz | 1755 → 1770 MHz | 2160 → 2175 MHz |
| TITAN RTX | Memory +10 true MHz | 6801 → 6840 MHz, approximately +9.75 true MHz | 7001 → 7041 MHz |
| TITAN Xp | Core +13 MHz | 1721 → 1733 MHz | 1911 → 1923 MHz |
| TITAN Xp | Memory +10 true MHz | 5508 → 5544 MHz, approximately +9 true MHz | 5705 → 5745 MHz |
| GTX 770 | Core +26 MHz, snapped request +27 | 1175 → 1201 MHz | Not separately recorded |
| GTX 770 | Memory +25 true MHz | 3505 → 3557 MHz, approximately +26 true MHz | Not separately recorded |

The TITAN tests first checked identity writes. Complete raw Pstates, V/F-table,
and lock buffers matched the originals after restoration. Independent
physical-clock counters also responded. The RTX captures additionally verify
that other-domain offset fields and all P-state voltage fields stayed unchanged.

On GTX 770, two load/restore cycles returned both offsets to zero. The mixed
clock-list regimes require deriving the boost grid from the contiguous upper
regime: 13.049 MHz, rather than the incorrect whole-list average of 5.523 MHz.
The tests use short workloads and do not establish maximum stable overclocks.

The local EXE/source package includes the raw measurements:

- [GTX 770 functional checks](experiments/kepler-validation-47212.json)
- [GTX 770 FAW verification](experiments/kepler-timing-writes-47212.json)
- [GTX 770 timing sweep and clock-lock attempts](experiments/kepler-timing-sweep-47212.json)
- [GTX 770 I2C identity reads](experiments/kepler-ncp4206-identity-47212.json)
- [TITAN RTX offset measurements](experiments/legacy-offsets-47212-0000-01-00.0.json)
- [TITAN Xp offset measurements](experiments/legacy-offsets-47212-0000-02-00.0.json)
- [580.97 voltage measurements](experiments/voltage-rails-20260906.json), explained in [VOLTAGE-RAILS-TITAN.md](VOLTAGE-RAILS-TITAN.md)

Public API references: [NVIDIA's Pstates20 declarations](https://github.com/NVIDIA/nvapi/blob/main/nvapi.h)
and [NVML API version history](https://docs.nvidia.com/deploy/nvml-api/change-log.html).

## Frequency locks and voltage rails

The R472 NVML frequency setter does not populate the NVAPI BoostLock table.
Druta reads RM command `0x20802077` instead: two 328-byte records identify
the minimum (`0x4C`) and maximum (`0x4B`) requests in kHz. The getter is
scoped to the measured TITAN RTX and driver 472.12. It uses a PCI-matched
Windows adapter handle and does not submit RM's paired setter command.

The production check held 1500 MHz with up to 100% CUDA utilization,
read an asymmetric 1200–1500 MHz range from a fresh process, and retained
that range while adding and removing an independent 900 mV V/F point lock.
Reset restored the original RM records, NVAPI lock, V/F table, and Pstates
byte for byte. The package includes the
[production frequency-lock measurements](experiments/legacy-frequency-production-47212.json).

On GTX 770, `nvmlDeviceSetGpuLockedClocks(1176, 1176)` and
`nvmlDeviceSetMemoryLockedClocks(3505, 3505)` both return Not Supported (3),
even as administrator. Application-clock and default-application-clock getters
also return Not Supported for graphics and memory; their setters were not
tested. A checked CUDA workload maintained P0/3505 MHz around timing writes;
this was not an enforced P-state lock. These results concern the tested APIs,
not every possible Kepler P-state-control mechanism.

Both TITAN cards on 472.12 reached 1112.5 mV with raised 1125 mV ceilings in two
raise/restore cycles. NVVDD +12.5 mV offsets moved the live voltage by
12.5 mV, and each ceiling independently clamped live voltage to 875 mV.
The idle floor also reached 875 mV and returned to its original value;
Pascal needs a verified identical re-send after a floor change on this driver.
See [the 472.12 rail report](VOLTAGE-RAILS-47212.md) for measured bases and
the separate per-field results.

The regular 1.2 V / XOC 1.5 V limit bounds and +200 / +500 mV offset bounds
are request ranges. These measurements do not establish a 1.15 V physical
maximum or promise that either board will deliver the top slider value.

Profiles and Undo restore their captured tuning controls; the separately
managed V/F hold remains until released. A successful stored V/F delta can
still be clipped in the evaluated curve by the driver's hardware ceiling.
The staging and apply results report those cases, and a default Pascal ramp
with no room for a whole clock bin reports no applicable change.

GTX 770 profiles record that the V/F table is inapplicable and restore ordinary
controls without requiring a curve. Live capture and Kepler → RTX → Kepler UI
switching passed; default profile replay and rejected cross-architecture curve
payloads are covered by hardware-free tests. Missing curves on other cards
remain incomplete. Windows sign-in profile application was not tested on GTX 770.

The TITAN UI callback checks exercised Max it, its single Undo action,
named-profile restoration, and Reset all on each card. All 13 checks per
card passed, and the original profile controls, raw V/F table, and lock
buffer were restored exactly. On RTX, the ramp has 19 points from 975 to
1093.75 mV and reaches 2160 MHz at 1093.75 mV.

The RTX MP2888A I2C ladder was measured under CUDA load with a 900 mV
V/F hold. Its +75 mV request increased rail-minus-VID by 45 mV. Requests
through +50 mV did not clear the probe's detection threshold; this is why
the control reports measured response separately from its requested offset.
The regulator's original raw offset of zero was restored and read back.

## Additional clock controls and card switching

The RTX per-domain checks used CUDA load and a 1.3-second settling interval
before sampling physical counters. Each +30 MHz request matched its stored
value, moved the corresponding counter, and restored its entire original
control buffer:

| RTX control | Physical clock before → after → restored, MHz |
|---|---:|
| XBAR | 1679.897 → 1709.896 → 1679.895 |
| Additional Memory Clock Offset | 6794.210 → 6824.185 → 6794.203 |
| SYS | 1754.899 → 1784.896 → 1754.899 |
| VIDEO | 1619.892 → 1649.897 → 1619.890 |
| LTC | 1409.999 → 1439.999 → 1409.999 |

On Xp, two +25 MHz Additional Memory Clock Offset cycles stored +25000 kHz
and moved the reported memory clock from 5508.00 to 5528.25 MHz. The ordinary
memory offset stayed zero. Two negative V/F point edits at a 900 mV hold
changed the evaluated curve from 1721.0 to 1708.5 MHz and live core from
1721 to 1708 MHz. Full domain, curve, and point-lock buffers restored exactly.

The real GUI switch checks alternated RTX's 128-point and Xp's 80-point
curves without disappearing curves or leaked GUI items. A clean curve
switches immediately; actual staged edits require the existing confirmation.
If the new GPU cannot initialize, the previous curve and edits remain intact.


GTX 770 switching likewise clears its unavailable curve and restores all 128
RTX points on return. No private NVAPI Kepler clock or rail write was attempted; the separately
validated I2C voltage path is described below.

## Memory timing write results

All observations use nvtune on driver 472.12. A stored field alone does not
establish usable live timing control.

| Card | Result | Restoration and workload check |
| --- | --- | --- |
| TITAN RTX | FAW 16 → 17 dropped | Original field unchanged |
| TITAN Xp | FAW 24 → 25 landed | Exact restoration confirmed |
| GTX 770 | FAW 32 → 33 twice; 15 delay fields in the sweep landed across broadcast and all four partitions | Every captured register restored exactly, including after idle → P0; 207 full 64 MiB comparisons passed during the sweep, plus 49 after final recovery |
| GTX 770 | CL 18 → 19 initially verified, then caused CUDA_ERROR_LAUNCH_FAILED and Display event 4101 | Driver recovered; original registers and a fresh checked load verified afterward; not classified as an ignored write |

GTX 770 sweep values (original → requested, each restored before the next):
RC 71→72, RFC 114→115, RAS 50→51, RP 22→23, RD_RCD 25→26,
WR_RCD 18→19, CDLR 10→11, WR 19→20, R2W_BUS 8→9, PDEX 15→16,
PDEN2PDEX 7→8, FAW 32→33, CCDL 2→3, CCDS 2→3 and RRD 8→9.

CL was not retried. WL, RPRE, WPRE and WRCRC were not tested after the CL
failure. W2R_BUS 12→13 and AOND 0→1 produced range warnings and were not
committed. Structural/training fragments, split refresh fields and inferred
TIMING22 addresses remained read-only. No force or daemon mode was used.
The CL result does not establish a POST-only restriction or rule out a change
that coordinates controller and DRAM programming. None of these short tests
establishes long-term stability.

## I2C regulator discovery: NCP4206

The author reports NCP4206-based I2C voltage control on GTX 770, GTX 780,
GTX 780 Ti, TITAN Black and the original TITAN using these Afterburner settings:

```ini
[Settings]
VDDC_Generic_Detection=0
VDDC_NCP4206_Detection=4:20h
```

These are candidate GPU families from user experience, not a claim that every
board variant uses the same regulator or bus routing. Afterburner's bus index
is not assumed to equal an NVAPI port number.

The local GTX 770 responds at 7-bit address 0x20 on NVAPI port 2: MFR_ID
(0x99, one byte) = 0x41, MFR_MODEL (0x9A, two bytes) = 0x3298 and
MFR_REVISION (0x9B, one byte) = 0x01. Ports 0, 1 and 3–7 did not respond
at that address. This confirms an accessible I2C device consistent with the
reported controller family. The manufacturer ID matches the
[onsemi NCP4206 datasheet](https://www.onsemi.com/download/data-sheet/pdf/ncp4206-d.pdf),
Table 11; the observed model/revision differ from its default 0x0208/0x03,
so Druta matches the measured PCI/subsystem and full observed identity tuple
rather than treating the manufacturer byte as sufficient.

The previous "no matching regulator profile" observation meant Druta shipped
no matching recipe; it did not establish that this card lacked I2C support.
Subsequent bounded writes validated the absolute voltage path on this board.
`ncp4206.py` writes VOUT_COMMAND (0x21, two bytes) before enabling bit 3 in
both VR Config registers (0xD2/0xD3); other bits and VOUT_CAL remain intact.
Auto clears both VID_EN bits before clearing the inactive command. Profiles
save the target command and Auto/manual mode, not a fictitious voltage offset.
Failure during a write attempts restoration of the captured command and mode.

The UI exposes 600..1281 mV in normal mode and 600..2000 mV in XOC, as
requested. The VR11 command itself represents only 375..1600 mV: requests
outside that encoding are rejected even in XOC, never wrapped or silently
clamped. Targets snap down to the 6.25 mV grid (1281 requests 1275 mV).
XOC expands a software envelope; it does not establish a 2 V hardware path.

Live checks stayed below the owner's 1350 mV test limit: 1250 and 1262.5 mV
requests read 1248.05 and 1263.67 mV through VMON (0xD7, measured LINEAR11
volts on this board). Verify uses a bounded +25 mV step under load and restores
the prior mode. UI Apply/Auto and profile round trips restored 0x21/0xD2/0xD3
exactly; 0xDD remained 3. Switching cards clears session verification. Those live
round trips explicitly excluded curve restoration. New Kepler profiles omit
the V/F requirement automatically; the corresponding default replay is tested
with fake hardware.

Support currently matches GTX 770 PCI 1184 / subsystem 1033196e and the
observed controller identity at port 2. The other reported GPU families remain
candidates, pending board-level validation. Evidence:
[production and UI checks](experiments/kepler-ncp4206-control-47212.json).
