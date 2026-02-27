# Social Preview Image Spec — COBOL Legacy Ledger

**Purpose**: GitHub social preview image (shown when the repo URL is shared on Twitter/LinkedIn/Slack/Discord).
**Dimensions**: 1280 x 640 pixels (GitHub's required 2:1 ratio)
**Output**: PNG, high quality

---

## Concept

A dark, technical hero image that communicates: **"Legacy COBOL wrapped with modern observability"**. It should feel like a premium developer tool — not a toy project, not a corporate slide.

---

## Visual Layout (Left-to-Right Composition)

### Left Third (~400px): COBOL Source Fragment

A translucent glass-morphism card showing a snippet of real COBOL source code. Use a monospace font (JetBrains Mono or similar). The code should be syntax-highlighted:

```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SETTLE.
      *> ──────────────────────────────
      *> COBOL CONCEPT: 3-Leg Settlement
      *> Clearing house mediates all
      *> inter-bank transfers via nostro
      *> accounts — real banking pattern
      *> ──────────────────────────────
       PROCEDURE DIVISION.
           PERFORM DEBIT-SOURCE-BANK
           PERFORM RECORD-CLEARING-HOUSE
           PERFORM CREDIT-DEST-BANK
```

Colors for syntax highlighting:
- Keywords (IDENTIFICATION, PROGRAM-ID, PROCEDURE, PERFORM): purple/violet (#a78bfa)
- Divisions (DIVISION): cyan (#22d3ee)
- Comments (lines starting with `*>`): gray italic (#6b7280)
- Regular text: white (#e2e8f0)

The card should have a subtle glass effect: slightly transparent background (rgba(15, 20, 40, 0.7)), blurred backdrop, thin white border (rgba(255,255,255,0.08)), rounded corners (12px).

### Center: Hub-and-Spoke Network Diagram

The centerpiece. A stylized version of the 6-node banking network:

- **CLEARING** node at the center — slightly larger, lavender/white glow (#c4b5fd)
- **5 bank nodes** arranged in a pentagon around it:
  - BANK_A (top-left): blue (#3b82f6)
  - BANK_B (top-right): green (#22c55e)
  - BANK_C (bottom-right): amber (#f59e0b)
  - BANK_D (bottom-left): violet (#8b5cf6)
  - BANK_E (left): pink (#ec4899)

Each node should be a glowing circle (16-24px radius) with a subtle outer glow in its color. Spoke lines connect each bank to CLEARING — thin lines (1-2px) in a dim version of the bank's color, with subtle animated-looking dashes or glow pulses to suggest data flow.

One spoke (e.g., BANK_A → CLEARING → BANK_B) should be highlighted brighter with a visible "packet" dot moving along it — suggesting an active settlement in progress.

### Right Third (~400px): Stats / Identity

Stack these elements vertically, right-aligned or centered within the right third:

**Title** (large, bold, white):
```
COBOL Legacy Ledger
```

**Tagline** (smaller, gray/muted, italic):
```
"COBOL isn't the problem.
 Lack of observability is."
```

**Key stats** (small badges or pill-shaped labels, spaced vertically):
- `10 COBOL Programs` — with a subtle green dot
- `372 Tests Passing` — with a subtle green dot
- `SHA-256 Hash Chains` — with a lock icon or chain icon
- `6-Node Settlement` — with a network icon
- `Python + FastAPI` — with a blue dot

**Bottom-right corner**: Small MIT license badge and GitHub star icon area (optional)

---

## Background

**Color**: Deep void (#0a0e1a to #0f172a gradient, top-left to bottom-right)

**Accents**: Two or three very subtle, large radial gradient circles in the background:
- One blue-ish glow (rgba(59, 130, 246, 0.05)) behind the left/center area
- One violet-ish glow (rgba(139, 92, 246, 0.05)) behind the right area

These should be barely visible — just enough to add depth to the dark background. Think "dark nebula" not "neon".

---

## Typography

- **Title**: Inter Bold (or similar clean sans-serif), 48-56px, white (#f8fafc)
- **Tagline**: Inter Italic, 18-20px, muted gray (#94a3b8)
- **Code**: JetBrains Mono or Fira Code, 12-14px
- **Stats**: Inter Medium, 14-16px, light gray (#cbd5e1)

---

## Style Keywords

- Glass morphism
- Dark mode developer aesthetic
- Technical but elegant
- Premium open-source project feel
- Similar vibe to: Vercel dashboard, Linear app, Raycast website

---

## What to Avoid

- Bright or colorful backgrounds — keep it dark and muted
- Cartoon/clipart COBOL imagery (no punch cards, no mainframe illustrations)
- Busy or cluttered composition — let the dark space breathe
- Generic "code on screen" stock photo look
- Any text smaller than 14px (won't be readable at social preview sizes)

---

## Reference Colors

```css
--bg-void:    #0a0e1a
--glass-bg:   rgba(15, 23, 42, 0.6)
--glass-border: rgba(255, 255, 255, 0.08)
--text-primary: #f8fafc
--text-muted:   #94a3b8
--bank-a:     #3b82f6  /* blue */
--bank-b:     #22c55e  /* green */
--bank-c:     #f59e0b  /* amber */
--bank-d:     #8b5cf6  /* violet */
--bank-e:     #ec4899  /* pink */
--clearing:   #c4b5fd  /* lavender */
--accent-kw:  #a78bfa  /* purple - COBOL keywords */
--accent-div: #22d3ee  /* cyan - COBOL divisions */
```
