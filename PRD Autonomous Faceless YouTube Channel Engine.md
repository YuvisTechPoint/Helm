# PRD: Autonomous Faceless YouTube Channel Engine

## Executive summary and reality check

We will build an autonomous engine that picks a niche, studies competitors, writes, produces, uploads and self-optimizes a faceless channel, with humans needed only for one-time setup and a small exception queue. A literal "zero humans, zero loopholes" system is not achievable on YouTube in 2026, and pretending otherwise is the biggest risk to the project. Three platform facts force this:

1. **Uploads are locked private until Google audits the API project.** Videos uploaded through `videos.insert` from unverified API projects created after 28 July 2020 are restricted to private, and each project must pass a compliance audit to lift this ([Google docs](https://developers.google.com/youtube/v3/docs/videos/insert)). The audit is a human-submitted form.
2. **Mass-produced content is not monetizable.** Since 15 July 2025, YouTube's Partner Program guidelines explicitly target mass-produced and repetitious "inauthentic" content ([BetaNews](https://betanews.com/2025/07/10/youtube-is-fighting-ai-slop-with-new-monetization-guidelines/)). Examples at risk include text-to-video-only clips, recycled footage, automated voiceovers over stock images, and high-volume low-effort AI uploads ([CineD](https://cined.com/youtube-set-to-crack-down-on-ai-slop-with-monetization-policy-update)). A naive automation pipeline produces exactly this.
3. **API quota is tight by default.** A default project gets 10,000 units a day, and the official reference prices one upload at 1,600 units, so roughly six uploads a day before analytics and research calls ([Google docs](https://developers.google.com/youtube/v3/docs/videos/insert)). More quota also requires the compliance audit ([revision history](https://developers.google.com/youtube/v3/revision_history)).

The product answer is **human-on-exception, not human-in-the-loop**. Every routine step runs unattended. The system escalates only on events no software can resolve: the one-time API audit, copyright or Community Guidelines strikes, monetization appeals, and expired credentials. Expected human time after launch: under 1 hour a month.

The second answer is **originality by design**. The pipeline's value is research and synthesis, not volume. Each video must carry a unique angle, sourced facts, custom data visuals and a script no other channel has, and a gate blocks anything that looks templated. Cadence is capped at 3 long-form videos and 5 Shorts a week, well below spam patterns.

## Research findings

The algorithm rewards viewer satisfaction, not upload volume or keyword stuffing, so the engine optimizes for satisfied viewers per impression.

### How the YouTube algorithm ranks videos

YouTube calls it a recommendation system with two goals: help viewers find what they want, and maximize long-term satisfaction ([Shopify summary](https://www.shopify.com/pk/blog/youtube-algorithm)). Each surface (Home, Suggested, Search, Shorts) has its own model, but all share that objective ([TubeCore](https://tubecore.xpanddigital.io/blog/youtube-algorithm-explained)). Recommendations are personalized per viewer, not a single ranked list of "best" videos.

| Signal | What it measures | What the engine controls |
| --- | --- | --- |
| Satisfaction | Post-watch surveys, "not interested", likes, dislikes, shares | Deliver the title's promise; strong ending; no bait |
| Click-through rate (CTR) | Clicks per thumbnail impression | Title and thumbnail variants |
| Retention (% viewed) | Share of the video watched; first 30 seconds weigh heavily | Hook, pacing, length fit to topic |
| Session and return visits | Whether viewers keep watching and come back | Series, playlists, end screens |
| Topic relevance | Match between video and viewer history | Tight niche, consistent sub-topics |

Two interactions matter for diagnosis. High CTR with weak retention reads as clickbait and can hurt reach; low CTR with strong retention usually means the packaging is the problem, not the content ([subsub.io](https://www.subsub.io/blog/youtube-algorithm-explained-how-youtube-recommends-videos-in-2026)). Retention is judged relative to length, so a shorter video with high average percentage viewed beats a long one with low retention ([TubeCore](https://tubecore.xpanddigital.io/blog/youtube-algorithm-explained)). Third-party write-ups also report Shorts runs on a separate engine from long-form and that consistent schedules give a small lift; treat both as unconfirmed by YouTube.

### Policies the engine must obey

| Policy | Rule | Engine requirement |
| --- | --- | --- |
| YPP inauthentic content (15 Jul 2025) | Mass-produced and repetitious content cannot be monetized ([Thurrott](https://www.thurrott.com/?p=323183)) | Originality gate, cadence cap, varied formats |
| Altered or synthetic (A/S) disclosure | Realistic AI-generated or altered content must be disclosed; settable via `status.containsSyntheticMedia` since 30 Oct 2024 ([revision history](https://developers.google.com/youtube/v3/revision_history)) | Set the flag on every upload that has realistic AI visuals or voice clones |
| Made for Kids | Must be declared on upload | Always set `madeForKids` explicitly |
| API Terms of Service | Unaudited projects are private-only; more than 10,000 units needs an audit | Audit before launch; quota budgeter |

### What the APIs expose

The YouTube Analytics API returns everything the self-diagnosis loop needs: views, average view duration, likes, subscribers gained and lost, plus `videoThumbnailImpressions` and its click rate ([metrics reference](https://developers.google.com/youtube/analytics/metrics)). Impressions count only when a thumbnail is visible for more than 1 second at 50% or more on screen ([YouTube Help](https://support.google.com/youtube/answer/7577430?hl=en)). Uploads, metadata edits, thumbnails and playlists run through the Data API. YouTube Studio's thumbnail "Test & Compare" is not assumed to be available by API; the engine runs its own sequential tests instead.

## Niche research

Default launch niche: **applied psychology explainers** (behavioral and Jungian psychology, aimed at English-speaking US, UK, Canada and Australia viewers), with personal-finance concepts as the fallback. The Niche Scout module re-runs this scoring on live data before the first upload and may override the pick.

### Scoring framework

Each candidate niche gets a 1–5 score on six factors, weighted to favor niches where automation can still add original value.

| Factor | Weight | How the engine measures it |
| --- | --- | --- |
| Revenue per 1,000 views (RPM) | 20% | Published 2026 niche RPM ranges, adjusted for target country |
| Demand | 20% | Search volume and views on top 50 recent videos for seed keywords |
| Competition gap | 20% | Share of top-ranking videos from channels under 50k subscribers; outlier ratio (views ÷ channel average) |
| Original-value fit | 20% | Can each video carry new research, data or synthesis without a face or on-camera demo? |
| Policy risk (inverse) | 10% | Exposure to medical, financial or news accuracy rules; copyright on source footage |
| Evergreen share | 10% | Share of top videos still earning views after 12 months |

RPM depends heavily on viewer country, so the engine writes in English and targets high-ad-rate countries; Indian-audience RPM runs far below the ranges below.

### Candidate niches (preliminary scores)

RPM ranges are third-party 2026 estimates and vary by source; scores are this PRD's preliminary judgment.

| Niche | Reported RPM (USD) | Competition | Original-value fit | Policy risk | Score /5 |
| --- | --- | --- | --- | --- | --- |
| Applied psychology explainers | $6–14 ([Kineclip](https://kineclip.com/blog/faceless-youtube-ideas-that-make-money-2026/)); Jungian sub-niche \~$7 ([ShortsFast](https://shortsfast.com/blog/best-faceless-youtube-niches-2026/)) | Medium | High: studies, frameworks, animated diagrams | Low–medium | 4.1 |
| Personal finance concepts | $15–30 ([Kineclip](https://kineclip.com/blog/faceless-youtube-ideas-that-make-money-2026/)) | High | High: data, calculators, charts | High (financial accuracy) | 3.8 |
| History mini-documentaries | $5–12 ([EasyViral](https://easyviral.ai/blog/15-faceless-youtube-channel-ideas-ranked-by-rpm-2026)) | Medium | High: maps, timelines, primary sources | Medium (archival rights) | 3.7 |
| Literary analysis | \~$9 with about 10k competing channels ([ShortsFast](https://shortsfast.com/blog/best-faceless-youtube-niches-2026/)) | Low | Medium: needs strong original takes | Low (quote limits) | 3.6 |
| Real estate market analysis | $12–30 ([ShortsFast](https://shortsfast.com/blog/best-faceless-youtube-niches-2026/)) | Medium (faceless) | Medium: public market data | Medium | 3.5 |
| Horror and story narration | $4–8 ([Kineclip](https://kineclip.com/blog/faceless-youtube-ideas-that-make-money-2026/)) | Medium | Low: easily templated | High (inauthentic-content flags) | 2.4 |
| Sleep sounds and ambience | \~$11 ([ShortsFast](https://shortsfast.com/blog/best-faceless-youtube-niches-2026/)) | High | Very low: repetitive by nature | Very high (repetitious content) | 1.8 |

Why psychology wins for a no-human system: it combines medium competition with a large evergreen audience, every video can cite real studies and frameworks (provable originality), and errors carry less legal and safety risk than finance or health. Finance pays roughly twice as much per view but needs a stricter fact-check gate and disclaimers, so it is the fallback if the scout finds psychology saturated in the target sub-topics.

Excluded outright: niches that only work as reuploads, compilations, AI news rewrites, or looped content, since these are the formats the July 2025 policy targets.

## Competitor analysis

The Competitor Analyst learns from "outlier" videos (videos that beat their own channel's average by 3x or more) rather than from big channels, because outliers show what the topic and packaging did, not the brand.

### Method

1. **Discover.** Run Data API searches for 30–50 seed keywords, keep channels whose recent uploads match the niche, and cap the tracked set at 100 channels.
2. **Collect.** Pull each channel's last 50 uploads with title, description, tags, duration, publish time, views, likes and comment counts. Snapshot daily to measure view velocity.
3. **Score outliers.** Outlier ratio = video views ÷ median views of that channel's last 20 videos, measured at the same age (7 and 28 days).
4. **Extract patterns.** An LLM and a vision model label every outlier on title structure, emotional trigger, topic cluster, thumbnail composition, text length, color contrast, video length and posting time.
5. **Synthesize.** Produce a weekly Pattern Report: which topics, title formulas and thumbnail styles over-index among outliers, and which gaps (high-demand topics with few strong videos) are open.

Compliance limit: the YouTube API does not provide other channels' captions or video files, and downloading or scraping them breaches YouTube's Terms. The analyst works from public metadata and thumbnails only; any transcript-level insight must come from a licensed third-party data provider.

### What the analyst will look for

These are common patterns among successful faceless explainer channels; the analyst must confirm or reject each with data before the engine adopts it.

| Pattern | Typical form | How the engine replicates it without copying |
| --- | --- | --- |
| Curiosity-gap titles | "Why smart people…", "The psychology of…" | Title generator trained on outlier structures, filled with our own topic |
| Simple, high-contrast thumbnails | One figure or object, 2–4 words, bold color | Template system with a distinct channel palette and original illustrations |
| Fast hook | Payoff promised in the first 10–15 seconds | Hook scorer rejects scripts that delay the promise |
| Series and franchises | Recurring formats viewers binge | Series planner groups topics into playlists |
| Length fit | Long enough to cover the promise, no padding | Length set per topic from outlier durations |
| Shorts as discovery | Short clips pointing to long-form | One Short cut from each long video, linked back |

The engine never reuses a competitor's title, thumbnail, script or footage. Patterns are abstracted to structure, and a similarity check blocks outputs that match a competitor asset too closely.

## Goals, non-goals and success metrics

The product succeeds if the channel reaches YouTube Partner Program eligibility within 9 months with no policy strikes and under 1 hour of human time a month.

**Goals**

- Run niche selection, research, scripting, production, upload and optimization end to end without routine human input.
- Produce content that passes YouTube's originality bar and qualifies for monetization.
- Detect underperformance automatically, find the root cause and apply a fix within 72 hours.
- Stay inside YouTube's Terms, API quota and disclosure rules at all times.

**Non-goals**

- Running multiple channels from one system (v2).
- Buying views, subscribers or engagement, or using bots to comment, like or watch. These breach YouTube's fake-engagement policy and are permanently banned in this product.
- Uploading through browser automation to dodge the API audit.
- Reuploading or lightly editing other people's content.

**Success metrics** (targets, to be recalibrated after the first 30 videos)

| Metric | Target | Source |
| --- | --- | --- |
| Impressions click-through rate | ≥ 5% on long-form after 28 days | Analytics API |
| Average percentage viewed | ≥ 40% long-form, ≥ 70% Shorts | Analytics API |
| Subscribers gained per 1,000 views | ≥ 3 | Analytics API |
| Partner Program eligibility | 1,000 subscribers + 4,000 public watch hours in 12 months, reached by month 9 | Channel stats |
| Policy strikes and limited-ads flags | 0 | Data API status, email alerts |
| Pipeline success rate | ≥ 95% of scheduled videos published on time | Orchestrator logs |
| Human time | < 1 hour a month after launch | Exception queue log |

## System architecture

The engine runs as three loops: a weekly planning loop, a per-video production line, and a continuous learning loop that feeds results back into planning.

&#91;embedded content: system architecture · 3 stages, 12 agents, 1 feedback loop\]

A script that fails the quality gate goes back for rewriting at most twice, then the topic is dropped. The Diagnostician's findings update topic weights, hook rules and the CTR model, and it edits live videos' metadata through the Publisher. Module IDs (M1–M14) are specified in the next section.

## Functional requirements

Fourteen modules, each a separately deployable agent with a typed input and output, so any one can be retried or replaced without touching the rest.

| ID | Module | Must do | Output |
| --- | --- | --- | --- |
| M1 | Setup and credential vault | Store Google OAuth refresh token, LLM, TTS and image API keys encrypted; refresh tokens automatically; alert 7 days before any expiry | Valid credentials on demand |
| M2 | Niche Scout | Score candidate niches with the Section 3 framework on live data; re-run quarterly | Chosen niche + sub-topic map |
| M3 | Competitor Analyst | Track up to 100 channels; compute outlier ratios daily; weekly Pattern Report | Patterns, topic gaps |
| M4 | Topic Planner | Keep a 30-day backlog ranked by demand × gap × fit; group into series; never repeat a covered topic | Content calendar |
| M5 | Research and fact engine | Gather 5+ credible sources per video (peer-reviewed studies, books, official data); store citations; extract claims with source links | Research brief with citations |
| M6 | Script writer | Write a hook in the first 15 seconds, a structure that pays off the title, and a clear ending; target length from M3 data; vary format between videos | Script + Short cut-down |
| M7 | Originality and quality gate | Block a script if similarity to competitor titles and thumbnails, or to our own past scripts, exceeds threshold; fact-check every claim against M5 sources; score hook, clarity, payoff; max 2 rewrites, then drop topic | Pass, rewrite or reject |
| M8 | Voice | Generate narration from a licensed, consistent TTS voice; normalize loudness to about −14 LUFS; no cloned real voices | Audio track |
| M9 | Visuals and edit | Build original motion graphics, diagrams and licensed stock or AI imagery; captions burned in for Shorts; licensed music only; render 1080p or 4K | Final video files |
| M10 | Title and thumbnail | Generate 3 title and 3 thumbnail variants in the channel style; score with a CTR model trained on M3 outliers and our own history | Ranked packaging set |
| M11 | Publisher | Upload via resumable `videos.insert`; set title, description with sources, tags, category, language, `madeForKids`, `containsSyntheticMedia`, chapters, playlist, scheduled publish time; respect quota budget | Published video ID |
| M12 | Analytics collector | Pull per-video metrics at 2, 24, 48 hours and 7, 28 days, plus traffic sources, retention curve and audience geography | Metrics store |
| M13 | Diagnostician and optimizer | Run the Section 8 loop; apply allowed fixes automatically | Fix log |
| M14 | Orchestrator and exception queue | Schedule every job; retry with backoff; dead-letter failed jobs; send the human a single alert for anything only a person can resolve | Run logs, alerts |

### Cross-cutting requirements

- **Idempotency.** Every job carries a run ID, so a retry can never create a duplicate upload.
- **Quota budgeter.** Tracks Data API units in real time and reserves enough for the day's scheduled uploads before allowing research calls.
- **Cadence cap.** At most 3 long-form videos and 5 Shorts a week, published at the times M12 finds best for the audience.
- **Kill switch.** Any strike, policy email or limited-ads flag pauses all publishing until the exception is cleared.
- **Full audit trail.** Every script, source list, asset licence and metadata change is stored for appeals.

## Self-diagnosis and auto-optimization

When views fall short, the Diagnostician finds which stage of the funnel broke (impressions, clicks, watching, or returning), fixes that stage only, and measures the result before changing anything else.

### Trigger rules

A video is flagged when, at the same age, it falls below 50% of the channel's median views for its last 10 videos, or below the niche benchmark from M3. The whole channel is flagged when 7-day views drop 30% or more against the prior 28-day average. Diagnosis runs at 48 hours, 7 days and 28 days after publish; nothing is judged before 48 hours, because early data is noise.

### Root-cause table

The engine reads the funnel in order and stops at the first broken stage.

| Symptom | Likely root cause | Automatic fix | Re-check after |
| --- | --- | --- | --- |
| Few impressions, normal CTR and retention | Topic has low demand, or YouTube can't place the video with an audience | Down-weight that topic cluster in M4; improve title and description keyword match to proven search terms; add to a relevant playlist | Next 3 uploads |
| Normal impressions, CTR under 3% | Packaging: title or thumbnail not compelling | Swap to the next-ranked title, then thumbnail, one at a time | 72 hours each |
| Good CTR, retention under 30% in first 30 seconds | Hook does not confirm the promise, or clickbait mismatch | Tighten title to match content; raise hook-score threshold in M6 for future videos | Next 3 uploads |
| Steady drop mid-video | Pacing or padding | Lower target length for the cluster; add pattern breaks (visual changes every 20–40 seconds) in M9 | Next 3 uploads |
| Strong views, few subscribers | No reason to return | Add series framing and end screens; link the next video in the series | Next 5 uploads |
| Traffic mostly from low-RPM countries | Language or topic attracts the wrong geography | Shift topic weights toward clusters with high-RPM audiences | Next 30 days |
| Sudden channel-wide drop with normal metrics | Platform change, seasonality, or a hidden policy issue | Check for strikes, limited ads and policy emails; compare against M3 competitors; if competitors also dropped, hold steady | 7 days |

### Rules that keep the loop honest

1. **One change at a time per video**, with a timestamped log, so cause and effect stay clear.
2. **Wait windows are fixed**: 72 hours for a packaging change, 3 uploads for a content change.
3. **Rollback** any change that does not beat the previous version.
4. **Learn across videos.** Every result updates the CTR model in M10, hook scoring in M6 and topic weights in M4, so the engine builds its own model of what the algorithm rewards for this channel.
5. **Allowed levers**: titles, thumbnails, descriptions, tags, chapters, playlists, end screens, publish times and future content settings.
6. **Forbidden levers**: deleting and re-uploading the same video, mass metadata rewrites, buying promotion outside YouTube's own ad tools, or any fake engagement.

If three consecutive 28-day cycles miss targets after fixes, the engine re-runs the Niche Scout and proposes a sub-niche pivot, which it executes automatically unless the human vetoes within 72 hours.

## Compliance, failure modes and loophole closure

Every known way the pipeline can fail has a prevention and an automatic response; only a handful of events need a person, and each reaches them as a single alert.

| Failure mode | Prevention | Automatic response | Human needed? |
| --- | --- | --- | --- |
| Uploads stuck private | Pass the API compliance audit before launch | Publisher refuses to schedule until audit status is confirmed | Once, at setup |
| Quota exhausted | Quota budgeter reserves upload units first | Defer non-critical calls to the next day | No |
| OAuth refresh token revoked or expired | App published in production status, not testing; token health check daily | Pause publishing, alert | Yes, re-consent (minutes) |
| Demonetization for inauthentic content | Originality gate, cadence cap, format variety, sourced research | Kill switch pauses uploads; diagnostician audits recent videos | Yes, appeal |
| Copyright claim or strike | Licensed music, stock and fonts only; licence stored per asset; no third-party footage | Kill switch; store evidence for dispute | Yes, dispute or appeal |
| Community Guidelines strike | Safety classifier on scripts and visuals; no medical or financial advice framed as instruction | Kill switch | Yes, appeal |
| Undisclosed AI content | `containsSyntheticMedia` set by rule on every upload with realistic AI imagery or voice | Block upload if field missing | No |
| Factual error in a video | Claim-level fact check against cited sources | On a credible correction comment, pin a correction and update the description | No |
| Render or upload failure | Health checks per stage | Retry 3 times with backoff, then dead-letter and use a backlog video | Only if backlog is empty |
| Third-party API outage (LLM, TTS, image) | Secondary provider configured for each | Automatic failover | No |
| Runaway costs | Monthly budget cap per provider | Pause new production at 90% of cap | No |
| Comment spam or abuse | YouTube's built-in filters plus a blocked-words list | Hold for review automatically | No |

### Hard rules (never configurable)

- No fake views, likes, comments, subscribers or watch-time schemes, and no bot accounts.
- No browser automation to bypass the API audit or quota.
- No downloading or reuploading other creators' videos.
- No impersonation of real people and no cloned real voices.
- Monetization and "made for kids" settings are always declared truthfully.

## Tech stack, cost and rollout

The stack is standard cloud components plus paid AI APIs; running cost is estimated at roughly $150–450 a month for 12 long-form videos and 20 Shorts.

### Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Orchestration | Temporal or Prefect on a small cloud VM | Durable workflows, retries, schedules |
| Data | PostgreSQL + object storage (S3 or GCS) | Metrics history, scripts, assets, audit trail |
| Language model | Claude API (primary) + one backup provider | Research synthesis, scripts, titles, diagnosis |
| Voice | Commercial TTS with a licensed stock voice | Consistent channel voice |
| Visuals | Remotion or FFmpeg for motion graphics and edit; licensed stock library; AI image generation with commercial rights | Original diagrams carry most of the originality |
| YouTube | Data API v3 (upload, metadata, playlists) + Analytics API (metrics) | Audited project required |
| Monitoring | Error tracking + email or Telegram alerts | Exception queue goes to one inbox |

### Monthly cost estimate (approximate, pre-launch)

| Item | USD per month |
| --- | --- |
| Language model calls | 50–150 |
| Text-to-speech | 20–100 |
| Stock and image generation | 30–100 |
| Compute and storage | 30–80 |
| Third-party analytics data (optional) | 0–50 |
| **Total** | **\~150–450** |

### Rollout

1. **Phase 0, setup (weeks 1–2).** Create channel and Google Cloud project, submit the API compliance audit, store credentials. Gate: audit approved.
2. **Phase 1, build (weeks 2–6).** Modules M1–M11 and M14; run Niche Scout and Competitor Analyst. Gate: 10 videos pass the quality gate in a private dry run.
3. **Phase 2, launch (weeks 7–14).** Publish at the capped cadence; M12 collects data. Gate: 30 videos live, zero policy flags.
4. **Phase 3, self-optimize (week 15 on).** Turn on M13 with automatic fixes. Gate: CTR and retention meet Section 5 targets for 2 consecutive months.
5. **Phase 4, monetize (target month 9).** Apply to the Partner Program once eligible; the application is a one-time human step.

### Open risks and questions

- Audit approval time is outside our control and could delay launch by weeks.
- YouTube may tighten AI-content rules further; the originality gate must be re-tuned when it does.
- Confirm the current `videos.insert` quota cost in the Cloud Console, since some sources still cite 100 units.
- Decide whether the human wants a 72-hour veto on niche pivots or full autonomy.

## Sources

- [YouTube Data API: videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- [YouTube Data API revision history](https://developers.google.com/youtube/v3/revision_history)
- [YouTube Analytics API metrics](https://developers.google.com/youtube/analytics/metrics)
- [YouTube Help: impressions and click-through rate](https://support.google.com/youtube/answer/7577430?hl=en)
- [BetaNews: YouTube's July 2025 monetization update](https://betanews.com/2025/07/10/youtube-is-fighting-ai-slop-with-new-monetization-guidelines/)
- [CineD: crackdown on mass-produced AI videos](https://cined.com/youtube-set-to-crack-down-on-ai-slop-with-monetization-policy-update)
- [Thurrott: YouTube defines inauthentic content](https://www.thurrott.com/?p=323183)
- [Shopify: how the YouTube algorithm works](https://www.shopify.com/pk/blog/youtube-algorithm)
- [TubeCore: YouTube algorithm explained](https://tubecore.xpanddigital.io/blog/youtube-algorithm-explained)
- [subsub.io: how YouTube recommends videos](https://www.subsub.io/blog/youtube-algorithm-explained-how-youtube-recommends-videos-in-2026)
- [Kineclip: faceless niches by RPM](https://kineclip.com/blog/faceless-youtube-ideas-that-make-money-2026/)
- [ShortsFast: best faceless niches 2026](https://shortsfast.com/blog/best-faceless-youtube-niches-2026/)
- [EasyViral: faceless channel ideas by RPM](https://easyviral.ai/blog/15-faceless-youtube-channel-ideas-ranked-by-rpm-2026)
