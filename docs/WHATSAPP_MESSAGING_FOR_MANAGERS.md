# Why the Contact Must Send “Hi” First — Manager Brief

**Business number:** +91 74483 64850 (BusinessCardScanner)  
**Last updated:** June 2026

This document explains **why** a contact must message our business on WhatsApp before a normal chat works — and **why CardSync cannot replace that step** by sending from our side.

---

## Short answer for leadership

**WhatsApp does not allow a business to open a normal chat with a stranger the way a person messages a friend.**

For a **visible, reliable conversation in Chats**, the **contact must send the first message** (e.g. “Hi”) to our business number. After that, CardSync can reply in the same thread.

This is **WhatsApp’s rule**, not a CardSync limitation. We tested it: when the contact sends “Hi” first, it works. When only we send first, the message often does not appear as a normal chat.

---

## Why WhatsApp requires the contact to message first

### 1. Anti-spam and user privacy

WhatsApp is built for **people**, not bulk business outreach. If any company could message any phone number and land directly in **Chats** without the user doing anything, users would get unwanted business messages like email spam.

So WhatsApp separates:

| Who sends first | What is allowed |
|-----------------|-----------------|
| **Business → unknown contact** | Only **pre-approved templates** (structured, reviewed by Meta) |
| **Contact → business** | Normal chat opens; business can reply like a real conversation |

The contact sending “Hi” is WhatsApp’s way of showing **they started the conversation**.

---

### 2. “Chats” vs business cold messages

| Contact action | What they see on their phone |
|----------------|------------------------------|
| **They send “Hi” first** | Thread in **Chats** with BusinessCardScanner — clear, familiar |
| **We send first (template only)** | WhatsApp may accept our API call, but the message often **does not show** like a normal chat — or is easy to miss |

We confirmed this in testing:

- **Contact sends Hi** → message thread works in Chats.
- **We send template on save only** → API says “sent,” but contact often does **not** see it in Chats.

---

### 3. We cannot send “Hi” from the business side instead

Managers sometimes ask: *“Can our system send Hi for them?”*

**No.**

| Message type | Can business send to a new number? |
|--------------|----------------------------------|
| Free text (“Hi”, “Thank you”, card details) | **No** — blocked until contact messages us |
| Approved template (`cardsync_card_received`) | **Yes** — but does not open the same Chats experience |

WhatsApp only allows **templates** as the first outbound message. Plain “Hi” from our number to a cold contact is **rejected by Meta**.

So the contact’s “Hi” **cannot** be replaced by our app sending “Hi” on their behalf.

---

### 4. The 24-hour conversation window

When a contact sends “Hi” (or any message) to our business number:

1. WhatsApp opens a **customer service window** (24 hours).
2. Inside that window, we can send **normal replies** (not only templates).
3. CardSync can auto-reply with their saved card details in the **same Chats thread**.

If the contact never messages us, that window **never opens**.

```
Contact sends "Hi"  →  Chats thread opens  →  24-hour window  →  CardSync replies
```

Without their “Hi”, we stay in **template-only** mode for first contact.

---

### 5. Why Meta’s demo looks easier

In Meta’s API Setup tutorial, messages often appear in Chats because:

1. Meta tells the tester to **message the test business number first** (“send Hi”).
2. Only **after that** does the demo send a reply.

It is the **same rule** — the tutorial just has the user message first. It is not a different or special API.

---

## What staff should do at events (recommended flow)

1. Scan the contact’s business card in CardSync.
2. Show the contact a **QR code** (or link) to open WhatsApp to our number.
3. Contact taps **Send** on the pre-filled message (e.g. “Hi, verify my number”).
4. Thread opens in **Chats** on their phone.
5. CardSync **auto-replies** with their card details in that chat.

**The contact only needs to do this once per number** to open the chat. After that, replies stay in Chats for 24 hours (and longer if they keep messaging).

---

## What we cannot promise without “Hi” first

| Expectation | Realistic? |
|-------------|------------|
| Contact sees our message in Chats without doing anything | **No** — not reliable |
| We send “Hi” from business instead of them | **No** — WhatsApp blocks it |
| We send approved template on save | **Yes** — API works, but visibility is limited |
| Contact sends Hi, then we reply | **Yes** — tested and works |

---

## FAQ

**Q: Why can’t CardSync fix this?**  
A: Inbox rules and first-message policy are enforced by **WhatsApp/Meta**, not by our code.

**Q: Is this only for India?**  
A: No. This applies globally on WhatsApp Business Platform.

**Q: Does the contact have to type “Hi” exactly?**  
A: No. Any first message to our number counts (Hi, Hello, or the pre-filled text from the QR).

**Q: Do we add them as a test recipient in Meta?**  
A: Not for our live +91 number. Test recipients are only for Meta’s sandbox US test phone. Our live number can message any number — but **Chats visibility** still needs contact-initiated messaging for the reliable path.

**Q: What if we only use template-on-save?**  
A: That is a valid **notification** path, but managers should not expect the same result as contact-sends-Hi-first. Many contacts will not see the message unless they search our number or message us.

---

## One-line message for managers

> **For a real WhatsApp chat the contact must send the first message. CardSync can reply automatically after that — but WhatsApp will not let us open Chats for them by sending “Hi” from our business account.**

---

## Technical reference (optional)

- CardSync QR / wa.me flow: contact scans → WhatsApp opens → they tap **Send** → webhook notifies backend → auto-reply sent.
- Template-on-save (business first): separate feature in Settings → Auto thank-you on WhatsApp; uses approved templates only.
- Display name **BusinessCardScanner** is currently **DECLINED** in Meta — business team should resubmit for approval to improve delivery trust.

*WhatsApp policies may change. Confirm delivery in Meta → WhatsApp Manager → Message logs when needed.*
