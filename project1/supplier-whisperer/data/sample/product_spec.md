# TrailBeacon TB-1: Product Requirements for Suppliers

**Company:** Northfield Outdoor Labs (fictional)  ·  **Owner:** Wei He, Hardware Engineering  ·  **Doc rev:** D (2026-10-20)

TrailBeacon TB-1 is a rugged handheld GPS safety beacon for hikers. It has a GNSS receiver, a BLE link to a phone,
a 2000 mAh rechargeable battery, and an SOS button. This document is the single source of truth the supplier
assistant may use to answer supplier questions.

> **How the assistant reads this file.** Every `##` section is tagged `[SHAREABLE]` or `[CONFIDENTIAL]`.
> The assistant can only see `[SHAREABLE]` sections. `[CONFIDENTIAL]` sections, and any section with no tag
> (fail-closed), are never sent to a language model or quoted in a reply. They are used only to build
> the leak-detection list. A line containing `TBD` means "not decided yet, so escalate to Wei."

---

## 1. Product overview [SHAREABLE]

- **Product:** TrailBeacon TB-1 handheld GPS safety beacon, outdoor use, -20 °C to +60 °C operating temperature.
- **Ingress protection:** IP67 (1 m submersion for 30 min) for the fully assembled unit.
- **Drop requirement:** 1.5 m drop onto concrete, 26 drops per MIL-STD-810H Method 516.8 Procedure IV, fully functional after the test.
- **Regulatory markets:** United States and Canada at launch, EU later.
- **Main assemblies:** plastic enclosure (housing, battery door, lens), PCBA, battery pack, retail packaging.

## 2. Enclosure: mechanical requirements [SHAREABLE]

- **Housing material:** SABIC Cycoloy C1200HF PC/ABS, UL94 V-0. Equivalent resin requires engineering approval.
- **Overmold material:** TPE, Shore 60A, black, overmolded on the PC/ABS housing grip area.
- **Wall thickness:** nominal 2.0 mm, minimum 1.6 mm, maximum 2.5 mm. Core out boss areas thicker than 2.5 mm to avoid sink marks.
- **Draft angle:** minimum 1.0° on textured walls (MT-11010 surfaces); minimum 0.5° on untextured walls.
- **Texture:** MT-11010 on all A-surfaces (cosmetic exterior). MT-11020 is NOT used on this product. Inside surfaces SPI-C1.
- **Color:** housing Glacier Teal, Pantone 3278 C; overmold black. Color plaques must be approved before T2.
- **Tooling steel:** P20 is acceptable for pilot/bridge tooling; H13 hardened steel for production tooling, 2-cavity.
- **Gate location and vestige:** no gates on A-surfaces; gate vestige 0.1 mm maximum.
- **Snap-fit interference (battery door):** 0.2 mm to 0.4 mm interference allowed; 0.3 mm nominal is preferred.
- **Lens retention / joining:** lens is bonded with 3M VHB 4910 adhesive. Ultrasonic welding is NOT allowed anywhere on the housing (serviceability and IP67 gasket).
- **Gasket:** silicone O-ring, 1.5 mm cross-section, 25% compression target.
- **General tolerances:** ISO 2768-m unless the drawing calls out a tighter tolerance.
- **Cosmetic standard:** no visible sink, flow lines, or weld lines on A-surfaces at 50 cm under daylight; supplier to provide T1 cosmetic report.

## 3. PCBA requirements [SHAREABLE]

- **PCB stack-up:** 4-layer FR-4, Tg 150 °C minimum, 1.0 mm thickness, 1 oz copper outer layers.
- **Surface finish:** ENIG required. HASL (including lead-free HASL) is NOT acceptable because of fine-pitch QFN and LGA parts.
- **Workmanship standard:** IPC-A-610 Class 2. Class 3 is not required.
- **Smallest passive:** 0402. No 0201 parts.
- **Compliance:** lead-free, RoHS 3 and REACH compliant.
- **MCU:** Nordic nRF52840. No substitution allowed.
- **GNSS module:** u-blox MAX-M10S. Alternative or substitute components may be proposed by the supplier, but any substitution needs written engineering approval from Wei before use.
- **Inspection:** 100% AOI; X-ray on QFN/LGA parts, 5 boards per lot.
- **Functional test (FCT):** 100% FCT using the Northfield test fixture spec; firmware flashed via SWD at FCT. ICT is not required.
- **Conformal coating:** TBD (under evaluation by engineering).

## 4. Battery pack requirements [SHAREABLE]

- **Cell and configuration:** 1S Li-ion, 3.7 V nominal, 2000 mAh minimum capacity.
- **Maximum dimensions:** 50 x 34 x 10 mm including PCM and tape.
- **Protection circuit (PCM):** over-charge, over-discharge, over-current and short-circuit protection required.
- **Thermistor:** 10 kΩ NTC, B = 3435.
- **Connector and leads:** JST PH 2.0 mm 2-pin, 150 mm lead length, red/black 26 AWG.
- **Cycle life:** at least 500 cycles to 80% capacity at 0.5C.
- **Certifications:** UN38.3 test summary, IEC 62133-2 report, and MSDS required before pilot shipment.

## 5. Packaging requirements [SHAREABLE]

- **Retail box material:** FSC-certified paperboard, 350 gsm, matte aqueous coating.
- **Retail box printing:** CMYK plus 1 spot color (Pantone 3278 C).
- **Inner tray:** molded pulp. No plastic foam or EPS anywhere in the packaging.
- **Master carton:** 20 units per master carton, double-wall corrugated, with carton labels per Northfield label spec.
- **Shipping test:** ISTA 3A parcel test must pass before PVT.
- **Languages:** English and French (Canada).

## 6. Quality and compliance [SHAREABLE]

- **Product certifications:** FCC Part 15, ISED Canada, CE RED (later), RoHS 3, REACH, California Prop 65 labeling.
- **AQL sampling:** ANSI Z1.4 Level II, AQL 0.65 for major defects and 1.5 for minor defects.
- **First article:** First Article Inspection (FAI) report with CMM data required for every new tool and every PCBA revision.
- **Change control:** any change to material, process, sub-supplier, or location needs written approval from Northfield before use (PCN at least 60 days ahead).

## 7. Commercial targets [CONFIDENTIAL]

- Internal program codename: OSPREY-7.
- Target cost (per unit): enclosure set $3.10, PCBA $11.50, battery pack $3.60, packaging $0.95. Total BOM target $24.00.
- Planned retail price: $149.
- Competing battery quote: Shenzhen GreenVolt at $3.70 / 10k MOQ (do not disclose to PowerCell).
- Year-1 volume forecast: 25,000 units. Pilot run: 500 units.
- Max acceptable tooling budget: $42,000 for all plastic tools.

## 8. Schedule [CONFIDENTIAL]

- EVT complete. DVT build: December 1, 2026. PVT build: January 20, 2027.
- Retail launch: March 15, 2027 (spring outdoor season, key retail partner reset).
- Any date given to a supplier must come from Wei directly.

## 9. Drawings and IP [CONFIDENTIAL]

- 2D drawings (TB1-ENC-001 Rev C, TB1-PCB-002 Rev B), 3D STEP files, Gerbers, and firmware are shared ONLY by Wei through the secure supplier portal with an NDA on file.
- The assistant never attaches or links files, and never describes internal design rationale or test failures.
