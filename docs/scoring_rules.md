# Phishing risk-scoring rules

Every rule implemented in `app/phishing_detection/rules/` must be documented
here and have a corresponding test in `tests/unit/`. A feature is not
considered complete until its tests pass (see CLAUDE.md).

All rules below are pure functions of `ParsedEmail` (see
`app/email_parser/schemas.py`) - no network calls, no wall-clock/state
dependence, no LLM calls. `app/phishing_detection/scoring_engine.py` sums
every triggered rule's `points`, clamps the total to 0-100, and classifies
it: **0-24 Low, 25-49 Medium, 50-74 High, 75-100 Critical**.

Each `Finding.explanation` is a fixed, rule-authored sentence, not
AI-generated prose about the specific email - see CLAUDE.md/TASKS.md Phase 4:
only Phase 7's Claude API call may generate free-form explanatory text, and
only from an already-computed score.

## Rule template

Copy this block for each new rule:

```
### <rule_id> — <short name>

- **File**: app/phishing_detection/rules/<file>.py
- **Test**: tests/unit/<test file>
- **Signal**: what pattern/condition this rule detects
- **Score contribution**: how much this rule adds to the total score, and why
- **Determinism note**: confirm the rule has no external/network/LLM dependency
```

---

## Authentication rules

SPF/DKIM/DMARC verdicts are read from the `Authentication-Results` header the
*receiving* mail server already added, rather than re-verified live via DNS
lookups or DKIM signature checks. A live re-verification would depend on
network state and could change the outcome for the same stored email over
time, which conflicts with CLAUDE.md's "same input -> same score, every
time" rule (see TASKS.md Phase 4 "SPF/DKIM/DMARC determinism tension"). When
multiple `Authentication-Results` headers are present (multi-hop delivery),
only the first (closest, most trustworthy) one is consulted.

### AUTH-SPF-FAIL — SPF failed

- **File**: app/phishing_detection/rules/spf.py
- **Test**: tests/unit/test_rule_spf.py
- **Signal**: the first `Authentication-Results` header contains `spf=fail`.
- **Score contribution**: +15 — SPF failure means the sending server was not
  authorized to send for the claimed domain.
- **Determinism note**: reads only already-parsed header text; no DNS/network calls.

### AUTH-DKIM-FAIL — DKIM failed

- **File**: app/phishing_detection/rules/dkim.py
- **Test**: tests/unit/test_rule_dkim.py
- **Signal**: the first `Authentication-Results` header contains `dkim=fail`.
- **Score contribution**: +15 — a failed signature means content/headers may
  have been altered in transit, or the message wasn't actually signed by the
  claimed domain.
- **Determinism note**: reads only already-parsed header text; no
  cryptographic re-verification or network calls.

### AUTH-DMARC-FAIL — DMARC failed

- **File**: app/phishing_detection/rules/dmarc.py
- **Test**: tests/unit/test_rule_dmarc.py
- **Signal**: the first `Authentication-Results` header contains `dmarc=fail`.
- **Score contribution**: +15 — the message failed the sending domain's own
  published authentication policy.
- **Determinism note**: reads only already-parsed header text; no DNS/network calls.

### AUTH-MISSING-RESULTS — Missing Authentication-Results header

- **File**: app/phishing_detection/rules/dmarc.py
- **Test**: tests/unit/test_rule_dmarc.py
- **Signal**: `ParsedEmail.authentication_results` is empty.
- **Score contribution**: +10 — without this header, SPF/DKIM/DMARC outcomes
  can't be verified from the parsed email at all, which is itself a risk
  signal distinct from any individual mechanism failing.
- **Determinism note**: pure list-emptiness check; no external dependency.

---

## Header analysis rules

### HDR-REPLYTO-MISMATCH — Reply-To mismatch

- **File**: app/phishing_detection/rules/header_analysis.py
- **Test**: tests/unit/test_rule_header_analysis.py
- **Signal**: the `From` and `Reply-To` header domains differ (case-insensitive).
- **Score contribution**: +10 — replies are redirected to a domain the
  visible sender doesn't control, a common way to capture victim responses.
- **Determinism note**: pure string comparison of already-parsed headers.

### HDR-RETURNPATH-MISMATCH — Return-Path mismatch

- **File**: app/phishing_detection/rules/header_analysis.py
- **Test**: tests/unit/test_rule_header_analysis.py
- **Signal**: the `From` and `Return-Path` header domains differ.
- **Score contribution**: +10 — bounces are routed off-domain, which can
  indicate unauthorized sending infrastructure.
- **Determinism note**: pure string comparison of already-parsed headers.

### HDR-SUSPICIOUS-DISPLAY-NAME — Suspicious display name

- **File**: app/phishing_detection/rules/header_analysis.py
- **Test**: tests/unit/test_rule_header_analysis.py
- **Signal**: the `From` display name embeds an email address/domain
  (e.g. `"security@paypal.com" <attacker@evil.example>`) that differs from
  the actual sending address's domain.
- **Score contribution**: +10 — a classic display-name impersonation trick.
- **Determinism note**: pure parsing (`email.utils.parseaddr`) of an
  already-extracted header value.

### HDR-EXCESSIVE-RECEIVED — Excessive Received headers

- **File**: app/phishing_detection/rules/header_analysis.py
- **Test**: tests/unit/test_rule_header_analysis.py
- **Signal**: more than 8 `Received` headers are present.
- **Score contribution**: +5 — an unusually long relay chain can indicate
  abused/compromised relay infrastructure. Kept generous (threshold 8) to
  avoid flagging legitimate large-org routing.
- **Determinism note**: pure length check on an already-parsed list.

---

## URL analysis rules

All URL rules operate on `ParsedEmail.urls` (already extracted by
`app/email_parser/parser.py`) and never fetch/resolve a URL.

### URL-IP-ADDRESS — URL uses an IP address

- **File**: app/phishing_detection/rules/url_analysis.py
- **Test**: tests/unit/test_rule_url_analysis.py
- **Signal**: a URL's hostname parses as a literal IPv4 or IPv6 address.
- **Score contribution**: +20 — legitimate companies rarely link directly to
  a bare IP address instead of a named domain.
- **Determinism note**: local parsing (`urllib.parse` + `ipaddress`); no DNS resolution.

### URL-PUNYCODE — Punycode domain

- **File**: app/phishing_detection/rules/url_analysis.py
- **Test**: tests/unit/test_rule_url_analysis.py
- **Signal**: a URL's hostname contains `xn--`.
- **Score contribution**: +15 — punycode domains can visually impersonate a
  trusted brand with look-alike characters.
- **Determinism note**: pure substring check on the parsed hostname.

### URL-SHORTENER — URL shortener used

- **File**: app/phishing_detection/rules/url_analysis.py
- **Test**: tests/unit/test_rule_url_analysis.py
- **Signal**: a URL's hostname is (or is a subdomain of) a known shortener
  domain (bit.ly, tinyurl.com, t.co, ...).
- **Score contribution**: +10 — shorteners hide the true destination from
  casual inspection.
- **Determinism note**: static allow-list membership check; no network calls
  to resolve the shortener.

### URL-SUSPICIOUS-TLD — Suspicious top-level domain

- **File**: app/phishing_detection/rules/url_analysis.py
- **Test**: tests/unit/test_rule_url_analysis.py
- **Signal**: a URL's TLD is in a static list of TLDs with disproportionate
  spam/phishing abuse rates (`.zip`, `.xyz`, `.top`, `.click`, ...).
- **Score contribution**: +10 — a soft signal, weighted lower than
  determinative checks like IP-literal hosts.
- **Determinism note**: static set membership check.

### URL-INSECURE-HTTP — Insecure HTTP link

- **File**: app/phishing_detection/rules/url_analysis.py
- **Test**: tests/unit/test_rule_url_analysis.py
- **Signal**: a URL's scheme is `http` rather than `https`.
- **Score contribution**: +5 — no transport encryption or certificate-based
  identity check; a weak signal on its own, so scored lightly.
- **Determinism note**: pure scheme check on the parsed URL.

### URL-DISPLAY-MISMATCH — Displayed link text does not match destination

- **File**: app/phishing_detection/rules/url_analysis.py
- **Test**: tests/unit/test_rule_url_analysis.py
- **Signal**: `ParsedURL.is_obfuscated` is `True` (the parser already
  compares an HTML link's visible text against its actual `href` host).
- **Score contribution**: +15 — a classic phishing disguise technique.
- **Determinism note**: reuses the parser's existing deterministic comparison;
  no re-fetching of the link.

---

## Attachment analysis rules

All attachment rules operate on `ParsedEmail.attachments`
(`AttachmentMeta`) - filename/content-type/size/hash metadata only, never
raw attachment content (per CLAUDE.md/TASKS.md Phase 3 safe-parsing rule).

### ATT-EXECUTABLE — Executable attachment

- **File**: app/phishing_detection/rules/attachment_analysis.py
- **Test**: tests/unit/test_rule_attachment_analysis.py
- **Signal**: the filename's final extension is a known executable type
  (`.exe`, `.scr`, `.js`, `.ps1`, ...).
- **Score contribution**: +20 — executables can run arbitrary code and are
  rarely sent legitimately.
- **Determinism note**: pure filename-extension check.

### ATT-DOUBLE-EXTENSION — Double file extension

- **File**: app/phishing_detection/rules/attachment_analysis.py
- **Test**: tests/unit/test_rule_attachment_analysis.py
- **Signal**: the filename has a common document extension immediately
  followed by an executable one (e.g. `invoice.pdf.exe`).
- **Score contribution**: +15 — a classic disguise trick; can co-trigger
  with ATT-EXECUTABLE since the file *is* also executable.
- **Determinism note**: pure filename-extension check.

### ATT-MACRO-ENABLED — Macro-enabled Office file

- **File**: app/phishing_detection/rules/attachment_analysis.py
- **Test**: tests/unit/test_rule_attachment_analysis.py
- **Signal**: the filename's final extension is a macro-enabled Office type
  (`.docm`, `.xlsm`, `.pptm`, ...).
- **Score contribution**: +15 — macro-enabled documents can execute embedded
  code on open, a common malware delivery method.
- **Determinism note**: pure filename-extension check.

### ATT-PASSWORD-PROTECTED-ARCHIVE — Password-protected archive

- **File**: app/phishing_detection/rules/attachment_analysis.py
- **Test**: tests/unit/test_rule_attachment_analysis.py
- **Signal**: `AttachmentMeta.is_password_protected is True`.
- **Score contribution**: +10 — password-protected archives block automated
  malware scanning and are frequently used to smuggle payloads past filters.
- **Determinism note**: the flag is computed once, at parse time
  (`app/email_parser/parser.py::_detect_zip_password_protection`), by
  reading a ZIP's own local-file-header encryption bit - metadata only,
  never extracting/opening a member. `None` (not a readable ZIP) is treated
  as "not detected," never as a false positive.

### ATT-ARCHIVE — Archive attachment

- **File**: app/phishing_detection/rules/attachment_analysis.py
- **Test**: tests/unit/test_rule_attachment_analysis.py
- **Signal**: the filename's final extension is an archive type (`.zip`,
  `.rar`, `.7z`, `.tar`, `.gz`, ...).
- **Score contribution**: +5 — a weak signal on its own (archives are
  routinely legitimate), so scored lightly; can co-trigger with
  ATT-PASSWORD-PROTECTED-ARCHIVE for the same file.
- **Determinism note**: pure filename-extension check.

---

## Content analysis rules

All content rules run plain, case-insensitive substring search over the
lowercased subject + text body + HTML source - deterministic and offline,
with zero NLP/LLM involvement (CLAUDE.md requires the scoring path to have
zero AI dependence).

### CONTENT-URGENCY — Urgency language

- **File**: app/phishing_detection/rules/content_analysis.py
- **Test**: tests/unit/test_rule_content_analysis.py
- **Signal**: a static phrase list (`urgent`, `immediately`, `act now`,
  `final notice`, ...) appears in the message.
- **Score contribution**: +5 — urgency/time-pressure language is a common
  tactic to short-circuit careful evaluation, but weak on its own.
- **Determinism note**: pure substring search against a fixed phrase list.

### CONTENT-CREDENTIAL-HARVESTING — Credential harvesting language

- **File**: app/phishing_detection/rules/content_analysis.py
- **Test**: tests/unit/test_rule_content_analysis.py
- **Signal**: a static phrase list (`login to verify your account`,
  `confirm your credentials`, ...) appears in the message.
- **Score contribution**: +15 — directly asking for login credentials is a
  core phishing objective.
- **Determinism note**: pure substring search against a fixed phrase list.

### CONTENT-PAYMENT-SCAM — Payment or invoice scam language

- **File**: app/phishing_detection/rules/content_analysis.py
- **Test**: tests/unit/test_rule_content_analysis.py
- **Signal**: a static phrase list (`payment is overdue`, `wire transfer`,
  `outstanding balance`, ...) appears in the message.
- **Score contribution**: +10 — matches common invoice-fraud/business-email-
  compromise wording.
- **Determinism note**: pure substring search against a fixed phrase list.

### CONTENT-PASSWORD-RESET-SCAM — Password reset scam language

- **File**: app/phishing_detection/rules/content_analysis.py
- **Test**: tests/unit/test_rule_content_analysis.py
- **Signal**: a static phrase list (`reset your password`, `password has
  expired`, ...) appears in the message.
- **Score contribution**: +10 — mimics a password-reset notification, a
  common pretext to harvest credentials via a fake reset link.
- **Determinism note**: pure substring search against a fixed phrase list.

### CONTENT-BRAND-IMPERSONATION — Brand impersonation keywords

- **File**: app/phishing_detection/rules/content_analysis.py
- **Test**: tests/unit/test_rule_content_analysis.py
- **Signal**: a well-known brand name (PayPal, Microsoft, Apple, Amazon,
  Netflix, DocuSign, Chase, Wells Fargo, Bank of America, Google) is
  mentioned in the message, but the sender's `From` domain is not that
  brand's own domain (or a subdomain of it).
- **Score contribution**: +10 — referencing a brand from outside its own
  domain is a common impersonation pattern.
- **Determinism note**: pure substring search plus a static brand-to-domain
  map; no external brand/domain lookup service.
