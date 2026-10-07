# PRD: Autonomous Lead-to-Client Acquisition Engine

Oct 7, 2026 · @moumita

## Overview

The product is an AI agent system that takes a business's service definition and, with no human in the loop, finds the prospects most likely to buy, reaches them by email, LinkedIn, WhatsApp and voice, handles replies and objections, and closes them into paying (or signed) clients. A human enters only after conversion, for onboarding and delivery.

**Problem.** Service businesses (agencies, consultancies, freelancers, B2B SaaS) lose a large share of founder or sales time to prospecting, list building, follow-ups and qualification. Most cold outreach is untargeted, so reply rates stay low and the work does not scale.

**Vision.** The owner writes what they sell, to whom, at what price and with what proof. The system then researches which segments convert best, sources and scores leads, writes personalised outreach, runs multi-touch sequences, talks to prospects, books or closes, and learns from every outcome to raise the conversion rate week over week.

**The handoff boundary.** The automation owns everything from "no lead" to "converted client". Conversion is defined per business in the Service Profile as one of:

- **Signed and paid** — the prospect accepted a proposal and paid a deposit or first invoice (best for fixed-price, low-ticket services).
- **Signed** — the prospect e-signed a proposal or contract.
- **Qualified meeting** — the prospect booked a call and passed qualification (for high-ticket deals where a human must close).

At that moment the client record, full conversation history and a briefing note go to a human, and the agents stop contacting that person.

**Product form.** A multi-tenant SaaS web app, so one platform can serve many businesses, each with its own Service Profile, channels, data and learning loop. A single-tenant version for one's own agency is the MVP (see Roadmap).

## Goals and success metrics

The north-star metric is **cost per converted client (CPCC)**, and the system optimises for the lead-to-client rate, not send volume. Benchmarks below are 2026 cold-email figures: the platform average reply rate is 3.43%, the top quartile is 5.5%+ and the top 10% is 10.7%+ ([Instantly 2026 report](https://instantly.ai/blog/ai-sales-agent-benchmarks-2026-the-complete-performance-report/)); agency senders typically see 2.5–4.5% ([Mailshake](https://mailshake.com/blog/cold-email-benchmarks-2026/)); and one 2-million-email study found only about 0.64% of sends produce an interested reply ([Apollo](https://www.apollo.io/insights/what-is-a-good-benchmark-for-reply-rates-in-cold-outreach)).

### Goals

1. Replace all pre-sale human work (research, list building, outreach, follow-up, qualification, scheduling, proposal, payment) with agents.
2. Beat top-quartile outbound performance by targeting narrow, high-intent segments instead of broad lists.
3. Learn continuously: every reply, objection, win and loss updates targeting, messaging and channel choice.
4. Stay compliant and protect sender reputation by design, so the system can run unattended for months.

### Success metrics (targets after a 60-day learning period)

| Metric | Definition | Industry baseline | Target |
| --- | --- | --- | --- |
| Inbox placement | Emails landing in primary inbox | Varies by sender | ≥ 90% |
| Reply rate | Replies ÷ delivered emails | 3.43% average | ≥ 5.5% (top quartile) |
| Positive reply rate | Interested replies ÷ delivered | \~0.64–1.5% | ≥ 2% |
| Positive reply → qualified | Interested leads that pass qualification | Not benchmarked | ≥ 50% |
| Qualified → converted | Per the conversion definition in the Service Profile | Not benchmarked | Set per business at onboarding |
| Spam complaint rate | Complaints ÷ delivered | Must stay < 0.3% | < 0.1% |
| Response latency | Time from prospect reply to agent reply | Not benchmarked | < 5 minutes, 24/7 |
| Human touches before conversion | Manual actions per converted client | Many | 0 (escalations excepted) |
| CPCC | Total tool, data and model cost ÷ converted clients | Not benchmarked | Below the business's target CAC |

### Non-goals

- Post-conversion work: onboarding, delivery and account management stay human.
- Mass B2C cold outreach to consumers' personal numbers or inboxes.
- Automating actions on platforms whose terms forbid it (see Compliance).
- Outbound AI voice calls to people who have not consented to be called.
- Deceiving prospects: the agent never claims to be human when asked.

## Users and use cases

The primary user is a service-business owner who wants clients without doing sales; the secondary user is the human who takes over after conversion.

| Persona | Who | What they do in the product | What they need |
| --- | --- | --- | --- |
| Owner (primary) | Founder of an agency, consultancy or freelance practice | Writes the Service Profile once, connects channels, sets budget and guardrails, reviews the dashboard weekly | Clients arriving with no sales work; confidence nothing embarrassing is sent |
| Delivery lead (post-handoff) | Account manager or the owner | Receives converted clients with full context and runs onboarding | A complete brief so they never ask the client to repeat themselves |
| Prospect (external) | Decision-maker at a target company | Receives outreach, asks questions, books, signs, pays | Relevant messages, fast honest answers, an easy opt-out |
| Platform admin (SaaS phase) | Operator of the multi-tenant platform | Manages tenants, abuse, deliverability pools, billing | Per-tenant isolation and kill switches |

**Core use cases**

1. *Cold start:* "I run a Shopify CRO agency, ₹50k–₹2L per project. Get me clients." The system proposes three ICP hypotheses, tests them in parallel, and shifts budget to the winner.
2. *Always-on pipeline:* the system keeps a target number of qualified conversations per week and throttles sourcing up or down to hit it.
3. *Inbound plus outbound:* a website visitor, form fill or content download enters the same funnel, already consented, and gets an immediate personalised reply.
4. *Re-engagement:* past "not now" prospects are re-contacted when a new trigger appears (funding, hiring, new site launch) and opt-outs are respected.
5. *Close without a call:* for low-ticket productised services, the agent answers questions, sends a proposal and a payment link, and converts in chat.

## End-to-end flow

A lead passes twelve automated steps, and the only human moment is the handoff after conversion. Cold contact happens by email; once a prospect replies, the conversation can move to WhatsApp or an AI voice call with their consent.

&#91;embedded content: end-to-end funnel · 12 steps, 1 learning loop\]

Leads can leave at any step: a low score sends them to a nurture pool, an unsubscribe adds them to global suppression on every channel, and "not now" schedules a re-contact on the stated date. Inbound leads (forms, chat, calls) enter at the Reply agent with consent already recorded.

## Functional requirements

Twelve modules carry a lead from "unknown" to "converted"; each is an agent or service with its own inputs, outputs and stop conditions. Priority: P0 = MVP, P1 = within 3 months of launch, P2 = later.

### M1. Service Profile (the only human input)

- **FR-1.1 (P0)** Guided onboarding captures: services and deliverables, pricing and packages, price floor and discount authority, ideal and anti-ideal clients, geographies and languages, case studies with numbers, testimonials, guarantees, FAQs, objections with approved answers, calendar link, payment and e-sign accounts, and the conversion definition (signed and paid / signed / qualified meeting).
- **FR-1.2 (P0)** The agent can draft the profile from the business website, past proposals and a 10-minute voice interview; the owner approves it once.
- **FR-1.3 (P0)** Everything agents say about the business must trace back to this profile. Facts not in it are never stated.
- **FR-1.4 (P1)** Upload of past client list and won/lost deals to seed the ICP model.

### M2. ICP and market research agent

- **FR-2.1 (P0)** From the profile and past clients, generate 3–5 ICP hypotheses, each with industry, company size, geography, role, buying trigger, pain, and the offer angle.
- **FR-2.2 (P0)** For each hypothesis, estimate market size (reachable contacts), likely intent signals and expected conversion drivers, citing sources.
- **FR-2.3 (P0)** Run hypotheses as parallel test cells; allocate volume with a multi-armed bandit (e.g. Thompson sampling) on positive reply and conversion rates, so budget flows to the segments that convert.
- **FR-2.4 (P1)** Look-alike modelling from converted clients (firmographic and technographic embedding similarity).

### M3. Lead sourcing

- **FR-3.1 (P0)** Pull companies and contacts from licensed B2B data providers via API (e.g. Apollo, Clay, Crunchbase, Google Places for local businesses), filtered by the active ICP cells.
- **FR-3.2 (P0)** Trigger-based sourcing: funding rounds, hiring for relevant roles, new website or tech-stack changes, new locations, ad activity, poor site performance, negative reviews — whichever triggers the profile maps to its services.
- **FR-3.3 (P0)** Inbound capture: website forms, chat widget, lead magnets and booking pages feed the same pipeline with consent recorded.
- **FR-3.4 (P0)** Deduplicate against CRM, existing clients, suppression list and previously contacted leads.
- **FR-3.5 (P0)** Never scrape platforms whose terms forbid it; only sources with a lawful basis and permitted use.

### M4. Enrichment and verification

- **FR-4.1 (P0)** Waterfall enrichment across providers for work email, role, seniority, company data and tech stack.
- **FR-4.2 (P0)** Verify every email before sending (reject invalid, risky catch-all above a threshold, role addresses where policy says so).
- **FR-4.3 (P0)** Research brief per lead: website summary, recent news, posts, job ads, visible problems relevant to the offer, with a source URL for every fact.

### M5. Lead scoring and prioritisation

- **FR-5.1 (P0)** Score = fit (ICP match) × intent (trigger strength and recency) × reachability (verified channel). Only leads above a threshold enter outreach; the rest wait in a nurture pool.
- **FR-5.2 (P1)** Score weights retrain weekly on actual outcomes (reply, qualify, convert).
- **FR-5.3 (P0)** Daily cap per tenant so volume never outruns deliverability capacity.

### M6. Personalisation and copy agent

- **FR-6.1 (P0)** Write each first touch around one specific, sourced reason to reach out, one relevant proof point from the profile, and one low-friction ask. Under 120 words, plain text, no links in the first email.
- **FR-6.2 (P0)** A separate critic agent checks every message before send: factual claims match sources, no invented numbers or names, tone, length, spam-trigger words, compliance footer. Failed messages are rewritten or dropped, never sent.
- **FR-6.3 (P0)** Follow-ups add new value (a case study, an insight, a short audit finding) rather than "bumping".
- **FR-6.4 (P1)** Language and cultural adaptation per region; A/B variants generated per test cell.

### M7. Multichannel outreach orchestrator

- **FR-7.1 (P0)** Email is the primary cold channel: multiple secondary sending domains, per-mailbox warm-up, randomised send times, per-mailbox daily limits, automatic pause on bounce or complaint spikes.
- **FR-7.2 (P0)** Default sequence: 3–4 touches over about 14 days, business hours in the prospect's time zone, stop on any reply on any channel.
- **FR-7.3 (P1)** WhatsApp and SMS only for leads who opted in (inbound forms, or a prospect who asks to move to WhatsApp), via the official WhatsApp Business API with approved templates.
- **FR-7.4 (P1)** AI voice agent: answers inbound calls 24/7, and places outbound calls only to leads who gave prior express consent (for example, "call me tomorrow at 4"). It identifies the business and that it is an AI at the start of each call.
- **FR-7.5 (P2)** LinkedIn: only through LinkedIn-approved APIs or partners (e.g. ads, matched audiences). Automated connection requests and DMs are out of scope because LinkedIn's User Agreement prohibits them.
- **FR-7.6 (P0)** Global cross-channel state: one prospect, one conversation, one owner agent; no double-touching.

### M8. Reply handling agent

- **FR-8.1 (P0)** Classify every inbound message: interested, question, objection, not now (with a date), wrong person / referral, unsubscribe, out of office, hostile, legal or complaint.
- **FR-8.2 (P0)** Reply within 5 minutes, 24/7, grounded only in the Service Profile and the lead's research brief.
- **FR-8.3 (P0)** Unsubscribe and "stop" are honoured instantly across all channels and all tenants' shared suppression where the law requires.
- **FR-8.4 (P0)** Referrals ("talk to Priya") create a new lead that cites the referrer; "not now" schedules a re-contact on the stated date.
- **FR-8.5 (P0)** When the agent would need a fact not in the profile, it says it will confirm and logs a profile gap (see Escalation below).

### M9. Qualification and objection handling

- **FR-9.1 (P0)** Configurable qualification criteria (budget band, authority, need, timeline) asked conversationally, never as a form dump.
- **FR-9.2 (P0)** Objection library from the profile (price, timing, "we have an agency", trust); the agent picks the approved answer and adapts wording, never the substance.
- **FR-9.3 (P0)** Disqualified leads get a polite close and a nurture tag, not more pushing.

### M10. Booking and closing

- **FR-10.1 (P0)** For "qualified meeting" conversion: book directly into the owner's calendar, send confirmation and reminders, and reduce no-shows with a pre-call brief.
- **FR-10.2 (P1)** For "signed" conversion: generate a proposal from approved templates and pricing rules, send for e-signature, follow up until signed or declined.
- **FR-10.3 (P1)** For "signed and paid": send a payment link (Stripe, Razorpay) for the deposit; conversion fires on successful payment.
- **FR-10.4 (P0)** Hard limits: the agent cannot go below the price floor, offer unapproved discounts, change scope or promise outcomes not in the profile.

### M11. Handoff to human

- **FR-11.1 (P0)** On conversion: create the client and deal in the CRM, attach the full transcript, research brief, agreed scope and price, and a one-page briefing; notify the owner by email, Slack or WhatsApp.
- **FR-11.2 (P0)** All automation for that contact stops immediately; the agent sends the client a warm hand-over message naming the human.

### M12. Learning and optimisation loop

- **FR-12.1 (P0)** Every outcome is logged against segment, trigger, message variant, channel, time and agent version.
- **FR-12.2 (P1)** Weekly auto-experiments on subject lines, angles, proof points, sequence length and send time; winners promoted, losers retired.
- **FR-12.3 (P1)** Monthly report with what changed and why, written for the owner.

### Escalation (the only exception to zero-human)

The agent pauses and escalates to an owner queue, with a 24-hour default SLA, for: legal threats or complaints, requests for custom pricing or scope beyond limits, press or partnership enquiries, a confidence score below threshold on a reply, and any message the critic agent fails twice. Until answered, the prospect gets a holding reply. Each escalation the owner resolves is added to the profile so it never escalates again.

## Agent architecture and tech stack

A durable workflow engine runs one long-lived workflow per lead and calls specialised agents for each step; no agent can send anything except through the policy guard. Splitting the work into narrow agents keeps each prompt testable and lets a cheap model handle routine steps.

&#91;embedded content: system architecture · 5 layers\]

The Copywriter and Critic are separate on purpose: the Critic never sees the writer's reasoning, only the draft and the sources, so it catches invented facts. The Conversation agent handles replies on every channel with one shared thread, and the Closer owns proposals, booking and payment links within the profile's hard limits.

### Suggested stack

| Layer | Recommended | Why |
| --- | --- | --- |
| Workflow orchestration | Temporal (or LangGraph for a lighter MVP) | Weeks-long sequences need durable timers, retries and exactly-once sends |
| Backend | Python (FastAPI) | Best agent and data tooling |
| Models | Claude Sonnet for writing and conversations; Claude Haiku for classification, scoring and extraction | Quality where prospects read it; low cost on high-volume steps |
| Database | Postgres + pgvector; Redis for queues and rate limits | One store for leads, embeddings and state |
| Front end | Next.js | Owner app and dashboard |
| Voice | Vapi or Retell on Twilio | Low-latency AI calls with transcripts |
| Evaluation | Recorded test conversations scored by rubric before each release | Prevents regressions in tone, accuracy and policy |
| Hosting | AWS or GCP with India (Mumbai) and EU regions | Data residency for DPDP and GDPR |

## Data model and integrations

Eight core entities hold the funnel, all scoped by `tenant_id`, with an append-only event log as the source of truth for learning and audit.

| Entity | Key fields | Notes |
| --- | --- | --- |
| Tenant / ServiceProfile | services, pricing, price\_floor, discount\_limit, icp\_rules, proof\_points, objections, faq, conversion\_definition, channels | Versioned; every agent message records the profile version it used |
| ICPCell | hypothesis, filters, triggers, offer\_angle, budget\_share, stats | Bandit allocation state lives here |
| Company | domain, industry, size, geo, tech\_stack, triggers\[\], sources\[\] | Shared enrichment cache per tenant |
| Lead | person, role, company\_id, email, phone, verification\_status, fit/intent/reach scores, stage, consent\[\] | One row per person per tenant |
| Consent | lead\_id, channel, basis (consent / legitimate interest / existing relationship), source, timestamp, evidence, withdrawn\_at | Required before WhatsApp, SMS or outbound AI calls |
| Conversation | lead\_id, channel, messages\[\], classifier labels, owner agent, state | One thread across all channels |
| Deal | lead\_id, proposal, price, e-sign status, payment status, converted\_at | Conversion fires from here |
| Event | type, actor (agent + version), payload, timestamp | Append-only; feeds analytics and the learning loop |

A global **Suppression** list (unsubscribes, complaints, "do not contact", existing clients, competitor domains) is checked before every send on every channel.

### Integrations

| Category | Purpose | Example providers (choose per region and budget) |
| --- | --- | --- |
| LLMs | Research, writing, critique, conversation, classification | Claude (Anthropic API); a small fast model for classification |
| B2B data | Companies, contacts, triggers | Apollo, Clay, Crunchbase, Google Places API |
| Email verification | Bounce prevention | ZeroBounce, NeverBounce |
| Email sending | Cold sequences with warm-up and rotation | Instantly, Smartlead, or Google Workspace / Microsoft 365 mailboxes via API |
| Messaging | Opted-in WhatsApp and SMS | WhatsApp Business Platform via a BSP; Twilio |
| Voice | Inbound and consented outbound AI calls | Vapi, Retell, Twilio Voice |
| Calendar | Booking | Cal.com, Calendly, Google Calendar |
| Proposals and e-sign | Signed conversion | PandaDoc, DocuSign, Zoho Sign |
| Payments | Paid conversion | Stripe, Razorpay |
| CRM | System of record and handoff | HubSpot, Zoho CRM, Pipedrive |
| Notifications | Handoff and escalations | Slack, email, WhatsApp to owner |

## Compliance, deliverability and guardrails

Only B2B email can be fully automated as a *cold* channel; WhatsApp, SMS and outbound AI voice must start from the prospect's consent, and automated LinkedIn DMs are off-limits. This shapes the funnel: email opens the conversation, and the prospect's reply unlocks the higher-converting channels. This section is product guidance, not legal advice; confirm with counsel in each market before launch.

| Rule | Applies to | What the system must do | Source |
| --- | --- | --- | --- |
| Gmail / Yahoo / Outlook sender requirements | All email, strictly at 5,000+/day to consumer inboxes | SPF, DKIM and DMARC on every sending domain; one-click unsubscribe honoured within 2 days; spam complaint rate kept under 0.3%, ideally under 0.1%. Microsoft enforces the same rules for Outlook since 2025. | [Close](https://help.close.com/technical-support/email-deliverability/requirements-for-bulk-email-senders), [Courier](https://www.courier.com/blog/email-sender-requirements) |
| US TCPA — FCC ruling of 8 Feb 2024 | Any outbound call using an AI-generated voice | Prior express consent of the called person before the call; identify the business; offer an opt-out on telemarketing calls. No cold AI calling. | [Orrick](https://infobytes.orrick.com/2024-02-16/fcc-ruling-determines-ai-calls-are-subject-tcpa-regulations/), [TLP](https://www.tlp.law/2024/02/09/fcc-makes-ai-generated-voices-in-robocalls-illegal/) |
| US CAN-SPAM | Commercial email to US recipients | Truthful headers and subject lines, sender's physical address, working opt-out | General knowledge — verify |
| EU / UK GDPR and ePrivacy | Prospects in the EU / UK | Lawful basis per country (legitimate interest for B2B email in some states, consent in others such as Germany); privacy notice at first contact; right to object and erasure | General knowledge — verify per country |
| India DPDP Act 2023 and DPDP Rules 2025 | Personal data of people in India | Rules notified Nov 2025; core notice, consent, security and rights obligations take effect 18 months later (around May 2027). Build for clear standalone notice, easy withdrawal and deletion on withdrawal now. | [DSK Legal via Mondaq](https://webiis10.mondaq.com/india/data-protection/1706722/legal-update-digital-personal-data-protection-rules-2025), [Hogan Lovells](https://www.hoganlovells.com/en/publications/indias-digital-personal-data-protection-act-2023-brought-into-force-) |
| India TRAI commercial-communication rules (TCCCPR) | Promotional calls and SMS in India | Use registered headers and designated number series; respect DND preferences | General knowledge — verify current TRAI rules |
| WhatsApp Business Policy | All business-initiated WhatsApp messages | Explicit opt-in before the first template message; Meta-approved templates outside the 24-hour service window; opt-out path in every marketing template | [Uptail](https://www.uptail.ai/blog/best-practices-for-whatsapp-business-messaging-the-rules-that-keep-you-effective-and-compliant), [ChatDaddy](https://chatdaddy.tech/blog/whatsapp-compliance-guide) |
| LinkedIn User Agreement §8.2 | Any LinkedIn activity | No bots or unauthorised automation to add contacts, send messages or scrape profiles | [LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a1341387) |

### Deliverability requirements

- Never send cold email from the primary business domain; use 3–10 look-alike secondary domains, each with 2–3 mailboxes.
- Warm up new mailboxes for at least 2–3 weeks before campaigns; keep each mailbox to a conservative daily cap and ramp slowly.
- Verify every address; pause a mailbox automatically if bounces or complaints spike, and rotate traffic away.
- Monitor Google Postmaster Tools and blocklists daily; alert the owner only if the system cannot self-heal.

### AI conduct guardrails

- The agent uses the owner's business name and a consistent persona, and answers truthfully if asked whether it is an AI.
- No fabricated facts, case studies, client names, urgency or scarcity.
- No contact with minors, consumers' personal numbers for cold outreach, or sensitive categories (health, finance hardship) as targeting signals.
- Kill switch per tenant, per channel and globally; every action is logged with the agent version that took it.

## Non-functional requirements and dashboard

The system must run unattended for weeks, so reliability, cost control and observability matter as much as conversion.

| Area | Requirement |
| --- | --- |
| Availability | Reply handling and voice: 99.9%; sourcing and batch research: 99% |
| Latency | Inbound reply to agent response < 5 min (p95); inbound call answered < 3 rings |
| Scale (SaaS phase) | 1,000 tenants, 2M leads, 100k sends/day without cross-tenant impact |
| Cost control | Per-tenant daily budget for data, sends and model tokens; hard stop when hit; cheap model for classification, strong model only for writing and conversations |
| Security | Encryption at rest and in transit; OAuth for mailboxes and CRMs, no stored passwords; secrets in a vault; SOC 2 controls by SaaS GA |
| Data residency | Region choice per tenant (India, EU, US) to support DPDP and GDPR |
| Isolation | Tenant data, sending domains and reputation never shared; one bad tenant cannot burn another's deliverability |
| Observability | Trace every agent decision (inputs, prompt version, output, critic verdict); replay any conversation |
| Evaluation | Offline test set of 500+ real replies and objections; a new agent version ships only if it matches or beats the current one on accuracy, tone and policy checks |
| Data rights | Export and delete a lead's data on request within 30 days, or sooner where law requires |

### Owner dashboard

- **Funnel view:** sourced → contacted → replied → positive → qualified → converted, per ICP cell, with drop-off between stages.
- **Money view:** spend by category, CPCC, pipeline value, revenue from converted clients.
- **Health view:** inbox placement, bounce and complaint rates per mailbox, domain reputation, channel status.
- **Conversations:** searchable live threads; the owner can watch but does not need to act.
- **Escalations queue:** the only to-do list, usually empty.
- **Experiments:** active tests, winners, and what the system changed this week.

## Roadmap, risks and open questions

Ship a single-tenant MVP that converts to a *qualified meeting* by email first, prove it on your own business, then add autonomous closing and only then open it up as SaaS. Each phase starts only when the gate before it is met.

&#91;embedded content: roadmap · 4 phases, 3 gates\]

Timelines assume a team of 2–3 engineers; mailbox warm-up alone fixes the earliest first send at about week 3–4.

### Key risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Sending domains get burned | Outreach stops; weeks to recover | Secondary domains, caps, auto-pause, daily monitoring (see Compliance) |
| Agent states something false | Lost deal, reputational or legal harm | Profile-only grounding, critic agent, eval set, escalation on low confidence |
| Regulatory breach on a channel | Fines, platform bans | Consent-gated WhatsApp, SMS and voice; counsel review per market before launch |
| Low conversion in the first weeks | Owner loses trust | Parallel ICP test cells, bandit allocation, 60-day learning period, inbound capture alongside outbound |
| Prospects react badly to AI | Lower reply rates | Honest disclosure when asked, high relevance, low volume per segment |
| Data or tool vendor changes terms or price | Pipeline gaps | Provider abstraction layer and waterfall enrichment |
| Runaway spend | Margin loss | Per-tenant budgets with hard stops; model routing by task |

### Open questions

- [ ] Which market first — India, US, UK/EU or a mix? It decides channels, data providers and compliance work.
- [ ] What counts as "converted" for your services: a booked qualified call, a signed proposal, or a paid deposit?
- [ ] Typical ticket size and whether a human call is needed to close it.
- [ ] Build the sending layer in-house or use a cold-email platform (Instantly, Smartlead) behind an abstraction?
- [ ] Monthly budget for data, sending tools and model usage during the learning period.
- [ ] Is the end goal an internal engine for your own business, or a SaaS product sold to others?
