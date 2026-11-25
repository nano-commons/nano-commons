# Mission 01: Verified PM2.5 for Northern Thailand (Open-Data Edition)

**Mission id:** `mission-01-pm25-north-th`
**Initiator:** Krittidet Chanthake
**Status:** Draft plan v0.2 · November 2026
**Principles:** No token. No central server. Open data in, open data out. **Zero cash required.**

---

## 1. Summary

Every haze season (roughly January to April), people in Northern Thailand make daily decisions based on PM2.5 readings: whether to send children to school, whether to work outdoors, whether to seal the house. The data they rely on has two weaknesses:

- **Official reference stations are accurate but sparse.** The Pollution Control Department's Air4Thai network does not reach most mountain villages and farming areas.
- **Low-cost sensor networks are dense but unverified.** Their readings drift, overestimate at high concentrations and high humidity, and fail silently, often at the very moments when accuracy matters most.

**Mission 01 builds nothing physical.** It uses PM2.5 data that is already public and asks volunteers to run Nano-Commons node consoles on computers they already own. The network independently cross-checks low-cost sensor readings against reference stations and against each other. Its consensus is tested with canary tasks whose answers come from official reference data. The output is an open, verified, reproducible record that nobody owns.

**What this mission proves:** strangers can verify public-interest data together, transparently, at zero cost and without an owner.

| Target | Stage 1: Historical backtest | Stage 2: Live shadow (haze season 2027) |
| :--- | :--- | :--- |
| Cost | 0 THB | 0 THB |
| Data | 3 past haze seasons (2024–2026) | Live hourly public feeds |
| Independent operators | ≥ 3 | ≥ 5 |
| Independent verifiers (canary issuers) | ≥ 2 | ≥ 2 |
| Zones | ≥ 4 | ≥ 4 |
| Output | Reproducible public report | Hourly verified verdicts + daily accuracy stats, labelled experimental |

---

## 2. Why start with open data

1. **No money, no waiting.** There is no hardware to buy, ship, install or repair. Work can start this month, and a live trial during the 2027 haze season becomes realistic.
2. **The ground truth already exists.** Air4Thai reference stations give the answers that canaries need. Thailand's 24-hour PM2.5 standard of 37.5 µg/m³, in force since 1 June 2023, gives a clear pass/fail line.
3. **The verification problem is real.** Peer-reviewed work found that a widely deployed low-cost sensor network in the region tracks reference trends but **significantly overestimates at higher concentrations**. Telling good low-cost readings from bad ones is exactly what this protocol is for.
4. **Everything can be reproduced.** Because every input is public, any outsider can re-fetch the same data, re-run the same mission and check every checkpoint hash. Trust does not depend on anyone's word, including the founder's.
5. **Sensors can follow later.** Deploying our own sensors becomes Mission 01b, a funded follow-up that builds on proven results.

---

## 3. What the mission delivers

For each **cell** (a 2 × 2 km grid square or a subdistrict) and each **hour**:

1. **Verdict:** whether the trailing 24-hour PM2.5 average is **above the national standard (ANOMALY)** or **not (NORMAL)**.
2. **Verified value:** the median of low-cost readings that passed validation, with an uncertainty band.
3. **Confidence:** the number of agreeing sensors and operators, the winning vote share, and the checkpoint status (`vouched`, `unverified` or `tainted`).
4. **Sensor health flags:** low-cost sensors that the network judges `SUSPECT` (stuck, spiking, drifting or disagreeing with neighbours and the reference).
5. **Audit trail:** checkpoint hashes, the fault log, alarms and rollbacks, all public.

The mission also publishes a **daily transparency sheet**: consensus accuracy against canaries, agreement with reference stations on held-out cells, and the number of quarantined operators.

**What it adds beyond the existing feeds**
- **Verified coverage:** areas without reference stations, from low-cost readings that pass cross-checks.
- **Public sensor-quality flags:** feedback that existing community networks can use.
- **A record no single party can quietly edit.**

---

## 4. Data sources

| Source | Role | Access | To confirm before use |
| :--- | :--- | :--- | :--- |
| **Air4Thai** (Pollution Control Department reference stations) | Canary answers; reference on held-out cells | Public website; also mirrored by aggregators | Terms of reuse; a stable endpoint for hourly station data |
| **OpenAQ** (aggregator; lists Air4Thai stations) | Programmatic access to reference and other feeds | Open API (free key) | Licence per upstream source; rate limits |
| **Low-cost community networks** in the region (e.g. DustBoy, operated with Chiang Mai University) | Main input to be verified | Public maps and feeds | Terms of reuse and redistribution; ask the operators for permission and collaboration |
| **Thai open government data** (data.go.th PM2.5 datasets) | Historical backfill and context | Open data portal | Dataset licence; whether values are station-measured or modelled |
| **Satellite aerosol products** (optional, later) | Context for cells without sensors | Free public products | Resolution and latency; for context only, never as canary truth |

**Rules for sources**
- Use only data whose terms allow processing and the publication of derived results.
- Attribute every source.
- Never republish raw feeds that the terms forbid us to redistribute. Publish derived verdicts and links back to the source instead.

---

## 5. How the mission runs on the protocol

### 5.1 Roles

| Role | Who | Does |
| :--- | :--- | :--- |
| **Data fetchers** | Several operators, independently | Pull the same public feeds for each hour, sign the raw snapshot and publish its hash |
| **Node operators** | Volunteers with a laptop or desktop | Run their own node console, execute validation tasks, sign their votes |
| **Verifiers** | At least 2 independent organisations or individuals | Issue canaries and hold the answers jointly; publish past canaries monthly |
| **Mission stewards** | 5–7 people from different groups | Change mission rules through the NCP process |
| **Data users** | Public, schools, media, researchers, agencies | Use the open output |

**The founder is one steward among several.** The founder must never be the only fetcher, the only operator or the only verifier, not even on day one.

### 5.2 Data flow

```text
Public feeds (Air4Thai, low-cost networks, open data)
        │   fetched independently by ≥ 2 fetchers per hour
        ▼
Signed raw snapshots ── hashes must match across fetchers ──▶ accepted input
        │
        ▼
One validation task per cell per hour
  observation = low-cost readings + humidity + neighbour cells (+ reference, if not held out)
  signed by the mission; commits observation_hash and assigned_workers
        │
        ▼
K operators across ≥ 3 zones ──▶ weighted consensus ──▶ checkpoint
        │                                          ▲
        ▼                                          │
Canaries (~10%, secret rate) ──▶ scored against reference truth ──▶ vouch / taint / alarm
        │
        ▼
Open output: verdicts, sensor flags, transparency sheet
```

### 5.3 Multi-fetcher attestation

The data comes from public websites, so the first risk is a fetcher altering it. Each hour, at least two independent fetchers pull the same sources and sign a hash of their snapshot. A task is built only from snapshots whose hashes agree.

When fetchers disagree, the hour is marked `unverified-input` and logged. A fetcher that disagrees repeatedly is quarantined, using the same reputation rules as for nodes. Because the sources are public, anyone can re-fetch and check after the fact.

### 5.4 Canary design: the heart of the mission

| Type | Where the answer comes from | Why it works |
| :--- | :--- | :--- |
| **A. Natural co-location** | Existing low-cost sensors within about 1–2 km of an Air4Thai station. The task uses only the low-cost readings, and the answer comes from the station. | Real field conditions, with nothing to install |
| **B. Historical replay** | Past hours with known reference values, re-issued as fresh tasks with timestamps removed | Drawn from the same distribution as real work, so workers cannot tell them apart |
| **C. Injected faults** | Real readings altered to look like known sensor failures (stuck values, spikes, dropouts). Expected verdict: `SUSPECT`. | Tests whether the network catches broken sensors |

**Integrity rules**
- **Hold-out cells.** A reference station used as a canary answer is never also an input for the same cell and hour. Otherwise the test would be circular.
- **Same pipeline.** All tasks, canary or real, go through the same pipeline with the same latency, for example processing at T + 1 hour.
- **Shared answers, delayed disclosure.** Canary answers are split between at least 2 verifiers. The full canary list is published monthly, after the fact.

### 5.5 Zones and caps

Suggested zones for Stage 1, to be confirmed with participants:
1. Chiang Mai city
2. Peri-urban and farmland (for example San Sai or Hang Dong)
3. Forest and highland (for example Mae Chaem)
4. A second province (for example Chiang Rai or Lampang)

With the default zone cap of 50% and a quorum of 65%, every accepted verdict needs agreement from at least two zones.

### 5.6 Federation without a central server

Peer-to-peer networking is not built yet, so Stage 2 uses a **pull-based federation**:

- Each operator runs their own node console and publishes signed votes and checkpoints to **their own** public feed, such as a free Git repository or a static web folder.
- A small **open aggregator** gathers the feeds, checks every signature and recomputes consensus. Anyone can run it.
- The aggregator is deterministic, so every copy produces the same result, and no copy carries authority. A mismatch between copies is itself an alarm.

---

## 6. Work needed in the protocol software

| # | Work item | Needed for | Size |
| :--- | :--- | :--- | :--- |
| 1 | **Source connectors** (Air4Thai via OpenAQ first; others as terms allow), plus raw snapshot hashing | Stage 1 | Medium |
| 2 | **Multi-value observations** (readings list, humidity, neighbours) | Stage 1 | Medium |
| 3 | **PM2.5 agent policy:** humidity correction, 24-hour rolling mean, outlier rejection | Stage 1 | Medium |
| 4 | **Third verdict `SUSPECT`** for sensor-health tasks | Stage 1 | Small |
| 5 | **Backtest runner:** replays historical seasons deterministically and produces a report with checkpoint hashes | Stage 1 | Medium |
| 6 | **Operator keys and signed votes** (today only missions sign) | Stage 2 | Medium |
| 7 | **Multi-fetcher attestation** (§5.3) | Stage 2 | Medium |
| 8 | **Multi-verifier canary issuance** with delayed disclosure | Stage 2 | Medium |
| 9 | **Feed publisher and open aggregator** (§5.6) | Stage 2 | Medium |
| 10 | Peer-to-peer transport and WebAssembly sandbox | Later missions | Large |

Items 1–5 are enough to begin. None of them needs money, only contributor time.

---

## 7. Timeline

| Period | Stage | Work | Measurable result |
| :--- | :--- | :--- | :--- |
| **Dec 2026** | 0 · Preparation | Inventory sources and confirm their terms. Contact low-cost network operators. Recruit ≥ 3 operators and 2 verifiers. Build items 1–4. | Source register with confirmed terms; volunteers confirmed |
| **Dec 2026 – Jan 2027** | 1 · Historical backtest | Build item 5. Replay the 2024–2026 haze seasons with type B and C canaries and type A co-location checks. Every operator re-runs it independently. | Public report; all operators reproduce identical checkpoint hashes |
| **Feb – Apr 2027** | 2 · Live shadow | Build items 6–9. Run live hourly with ≥ 5 operators and ≥ 2 fetchers. Publish verdicts labelled "experimental". | Daily transparency sheets; weekly summaries |
| **May – Jul 2027** | 3 · Evaluation | Full-season comparison against reference. Calibrate penalties. Publish findings and decide on Mission 01b (own sensors, grant-funded) and peer-to-peer. | Season report (CC0); decision record |

---

## 8. Cost

| Item | Cash cost | What is needed instead |
| :--- | ---: | :--- |
| Sensors | 0 | Existing public networks |
| Compute | 0 | Volunteers' existing computers, light load (a few tasks per cell per hour) |
| Hosting of results | 0 | Free Git hosting or static pages, one per operator |
| Data access | 0 | Public APIs and open data (a free API key where required) |
| Software | 0 | Contributor time on items 1–9 |
| **Total** | **0 THB** | About 5–10 committed volunteers |

Grants become relevant only for Mission 01b. A zero-cost Mission 01 also makes a far stronger grant application later, because it arrives with evidence.

---

## 9. Success criteria

| Metric | Stage 1 (backtest) | Stage 2 (live shadow) |
| :--- | :--- | :--- |
| Agreement with reference on held-out co-located cells (above or below 37.5 µg/m³, 24-hour) | ≥ 85% of hours | ≥ 85% of hours |
| Consensus accuracy on canaries | ≥ 90% | ≥ 95% |
| Injected faults caught (type C) | ≥ 80% | ≥ 90% |
| Independent operators reproducing identical checkpoint hashes | 100% | 100% of aggregator copies |
| Fetcher agreement on raw snapshots | n/a | ≥ 98% of hours |
| Cells covered that have no reference station | ≥ 15 | ≥ 15 |
| Independent operators / zones (no zone above 50%) | ≥ 3 / 4 | ≥ 5 / 4 |
| Open publication (CC0) | Backtest report | Hourly verdicts + daily stats |

---

## 10. Risks and responses

| Risk | Impact | Response |
| :--- | :--- | :--- |
| Data terms forbid reuse or redistribution | Source cannot be used | Confirm terms first; publish only derived verdicts with links; ask operators for permission and partnership |
| Upstream feed outage or format change | Missing hours | Several sources; mark gaps as `unverified-input`; never fill gaps silently |
| Circular validation (reference used as both input and answer) | Inflated accuracy | Hold-out rule (§5.4); publish the hold-out list |
| Fetcher alters data | Poisoned inputs | Multi-fetcher hash agreement; anyone can re-fetch and audit |
| The founder becomes the de facto centre | Breaks the charter; loses trust | From day one: ≥ 3 operators, ≥ 2 verifiers, ≥ 2 fetchers and several stewards. The founder never holds canary answers alone. |
| Results contradict official figures | Seen as adversarial | Present the mission as a complementary verification layer that uses official data as ground truth. Publish all methods. Invite agencies to observe. |
| Seen as competing with existing community networks | Lost goodwill and data access | Present it as a free quality-assurance service for those networks. Share sensor-health flags with their operators first. |
| Volunteer drop-off | Too few operators | Light compute load; clear setup guide; small rotating rosters |
| Someone launches a fake "PM2.5 token" | Public harmed | Repeated public statements that no token exists; signed releases only |
| Adaptive colluders learn to recognise canaries | Canaries stop catching them | Type B canaries drawn from real data, a secret rate and equal latency |

---

## 11. Non-negotiable principles

1. **No token and no tradable reward.** Contributors earn non-transferable credits and public credit in reports.
2. **No central server.** Every operator runs their own console. The aggregator is open and anyone can run it.
3. **Verified results are public domain (CC0).** Source data is used only as its terms allow, and always attributed.
4. **No one holds canary answers alone,** including the founder.
5. **Every alarm, rollback and rule change is logged and public.**

---

## 12. Next 30 days for the initiator

1. **Publish the repository and this plan.** Invite operators, verifiers and stewards openly.
2. **Build the source register.** Check the terms of Air4Thai, OpenAQ and the regional low-cost networks, and message their operators to propose collaboration rather than competition.
3. **Recruit the first group:** 3 node operators, 2 verifiers and 2 fetchers, from different organisations and at least 2 provinces.
4. **Ask the dev team to start work items 1–5** (connectors, multi-value observations, PM2.5 policy, `SUSPECT`, backtest runner).
5. **Set the date for the Stage 1 backtest report.** Aim for late January 2027, before the haze season peaks.

---

## Sources

- Thailand's 24-hour PM2.5 standard of 37.5 µg/m³, effective 1 June 2023: [Thai PBS World](https://www.thaipbsworld.com/?p=290375), [The Nation](https://nationthailand.com/in-focus/40015916), [The Nation, comparison with WHO](https://www.nationthailand.com/in-focus/40017734)
- Pollution Control Department release applying the 37.5 µg/m³ standard: [pcd.go.th](https://www.pcd.go.th/wp-content/uploads/2023/08/pcdnew-2023-08-31_03-49-50_720220.pdf)
- A low-cost regional network (DustBoy, PMS5003 sensor) overestimates at high concentrations; Air4Thai is the national reference network: [MDPI Atmosphere, 2025](https://www.mdpi.com/2073-4433/16/1/76)
- Thai open government PM2.5 datasets: [data.go.th](https://data.go.th/en/dataset/pm2-54)
- Air4Thai stations available through OpenAQ: [OpenAQ](https://explore.openaq.org/locations/225642)

*© 2026 Krittidet Chanthake and the Nano-Commons contributors. Licensed under CC BY-SA 4.0, in keeping with the Nano-Commons charter.*
