# Kashish Yoga — visual redesign

## Deliverables

- [Responsive interactive prototype](./index.html)
- [390px mobile preview](./mobile-preview.html)
- [1440px desktop SVG](./desktop-1440.svg)
- [390px mobile SVG](./mobile-390.svg)

The design uses Bodhi's calm mint/teal direction, airy spacing, sans-serif typography, rounded cards, and a clear visual hierarchy. Kashish's logo, photographs, wording, course details, and destinations are retained. Bodhi's logo, photographs, testimonials, and business content are not used.

This is a design prototype, not a live-site deployment or a native `.fig` document.

## Content preservation

The 23 original sections are retained in their original order. All original text is compared with the generated content for exact wording and ordering, ignoring only HTML whitespace. This includes:

- Seven yoga-style cards, 12 daily-schedule entries, four curriculum disclosures.
- Both accommodation options and all 18 course-date cards.
- Four teacher profiles and all 14 FAQ questions **and answers**.
- The original media, certification information, inclusions, exclusions, and contact/application links.

The content snapshot was captured on 6 October 2026. Dates, available spaces, and prices are a snapshot, not a live availability feed. The original website is the source of truth.

Existing source inconsistencies are deliberately not corrected: repeated multi-style training content, the Yin/SUP descriptions, duplicate 8:30 AM schedule entries, and the teacher-credential instruction remain as supplied. Correcting these would require a separate content decision.

Decorative stars and divider icons are replaced by spacing, borders, and cards. Duplicate desktop/mobile certificate imagery is displayed once. A hero photograph is reused from the original gallery. These are visual changes, not content deletions.

The certificate section uses an explicit two-column composition: graduation outcomes, supporting copy, and accreditation marks on the left; a contained collage and framed, uncropped certificate on the right. It stacks on mobile. Travel preparation uses four numbered cards rather than the source's decorative arrow images. Cards are displayed chronologically: before flying, arrival, during the stay, then going home. All original wording is retained; only the visual order of these travel cards changes.

## Design tokens

| Token | Value | Usage |
|---|---|---|
| Ink | `#123A3D` | Main headings, navigation |
| Muted | `#52666A` | Body text |
| Primary teal | `#176858` | Buttons, links, active states |
| Accent teal | `#207467` | Secondary headings |
| Mint | `#EAF8F2` | Hero and conversion areas |
| Paper | `#FFFDFA` | Main page background |
| Soft surface | `#F3F8F4` | Alternating sections |
| Border | `#DCE9E3` | Card and accordion outlines |
| White | `#FFFFFF` | Card backgrounds, primary button text |

Use Arial, available in both browsers and Figma, for reproducible typography.

| Style | Desktop prototype | Mobile prototype |
|---|---|---|
| Hero eyebrow | 12px bold, 0.15em tracking | Same |
| Hero headline | Up to 60px, line height 1.12 | 40px |
| Section heading | Up to 42px, line height 1.2 | 30px |
| Accent heading | Up to 36px | 26px |
| Card heading | 21px | 21px |
| Body | 17px, line height 1.65 | 15px |
| Card body | 15px | 15px |
| Button label | 12px bold | 12px bold |

## Layout and components

- Desktop reference width: **1440px**, content width: **1248px**, outer margins: **96px**.
- Mobile reference width: **390px**, outer margins: **24px**.
- Spacing scale: **8, 12, 16, 20, 24, 32, 48, 64, 72, 88px**.
- Standard cards: **24px radius**, **24px padding**, **1px border**.
- Buttons: pill shape, **52px minimum height**, with a subtle lift on hover.
- Header: sticky, soft background, logo, section links, and dates CTA.
- Desktop hero: two columns, course copy on the left; gallery photograph and video link on the right.
- Course dates: three columns on large desktop, two on intermediate widths, one on mobile.
- Accommodation, audience, and teacher cards: two columns on desktop, one on mobile.
- Original photographs are locally stored, proportionally resized to a maximum dimension of 1000px, and cropped visually within rounded containers.
- FAQ/curriculum: native keyboard-accessible HTML disclosures. The SVGs show expanded answers so the entire content is available in the design handoff.
- Mobile menu: accessible toggle with expanded state; closes on link selection and Escape.

Responsive breakpoints: **1050px** for intermediate card grids, **760px** for stacked layouts and mobile navigation.

## Prototype behavior

Run from this directory:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/` or `http://127.0.0.1:8765/mobile-preview.html`.

Section navigation and dates CTAs scroll locally. Booking and enquiry CTAs retain their original website destinations. WhatsApp opens the original course contact. No bookings, form submissions, or messages are sent by opening the prototype.

The source Vimeo embeds refuse playback on the local prototype domain. Video tiles therefore open the corresponding original Kashish page section in a new tab. The original video URLs remain recorded in the content model and the tiles' data attributes. This avoids broken video embeds and does not introduce replacement videos.

## Import into Figma

1. Create a blank Figma Design file.
2. Drag [desktop-1440.svg](./desktop-1440.svg) and [mobile-390.svg](./mobile-390.svg) onto the canvas.
3. Keep each import at its original width, 1440px or 390px.
4. Rename the imported groups “Kashish / Desktop” and “Kashish / Mobile”.
5. Create matching frames, then place the imported groups inside them.
6. Use the tokens above to recreate reusable buttons, cards, disclosures, and Auto Layout components as needed.

The SVGs contain vector shapes, SVG text nodes, and embedded raster photographs. They are **not flattened screenshots**, but Figma's importer may outline or regroup text and other elements. SVG import does not create native Figma components, text styles, Auto Layout, or prototype connections automatically.

These are full-page, long-form exports. For easier editing, duplicate the imported design and separate it into section frames. Font wrapping and expanded disclosure states mean the SVGs are layout mockups, not pixel-identical browser captures.

## Verification and regeneration

[validation.json](./validation.json) records the source-content comparison and SVG frame dimensions.

Automated tests cover exact source-content comparison, business-content counts, HTML assets/anchor targets, certificate/travel composition, and SVG structure/full-text coverage. Browser checks cover horizontal overflow at **320, 390, 768, 1024, and 1440px**. Mobile menu opening, Escape dismissal, and FAQ answer expansion were exercised.

```sh
python3 test_redesign.py
```

To rebuild from the existing source snapshot:

```sh
python3 build.py
```

The generator uses Python's standard library and macOS `sips`. Assets are cached locally. An uncached image download or conversion failure stops the build explicitly rather than silently replacing the image.

The existing dashboard project outside this directory is untouched. Live-site deployment, native Figma component creation, payment/form processing, and updating business content are outside this handoff.
