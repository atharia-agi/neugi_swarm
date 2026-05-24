# NEUGI Web Release Checklist (Shipping)

## 1) Content and Brand Consistency
- Verify `index.html`, `docs.html`, and `dashboard.html` use consistent positioning:
  - Production-grade
  - Reliability, governance, security
  - Avoid over-claim language
- Confirm all key CTAs are intentional and ordered:
  - Primary: start/use product
  - Secondary: architecture/docs
  - Tertiary: repository/changelog

## 2) Encoding and Text Integrity
- Ensure files are UTF-8 and render cleanly:
  - No mojibake characters (`â`, `Â`, broken dash/copyright)
- Spot-check:
  - Page `<title>`
  - Hero badge
  - Footer copyright
  - Proof chips / metric labels

## 3) Functional Link Validation
- Validate all nav and CTA links:
  - `dashboard.html`
  - `docs.html`
  - `wizard.html`
  - GitHub URL
  - External ecosystem links
- Confirm section anchors work:
  - `#architecture`
  - `#agents`
  - `#features`
  - `#ecosystem`

## 4) Trust and Proof Signals
- Confirm proof strip values are up to date:
  - release date
  - tests passing
  - security/governance claim
- If metrics changed, update:
  - subsystems
  - modules
  - LOC
  - tests

## 5) Visual QA (Desktop + Mobile)
- Header/nav does not overlap hero
- Hero CTA row wraps cleanly on narrow screens
- Cards keep compact 4-6px radius style
- No oversized icons or accidental spacing regressions

## 6) Final Technical Pass
- Run repo status and review only intended diffs
- Re-check no accidental formatting corruption
- Publish/deploy
- Post-deploy smoke check:
  - Home page
  - Docs page
  - Dashboard page

