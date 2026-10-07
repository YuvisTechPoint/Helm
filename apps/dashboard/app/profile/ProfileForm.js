"use client";

import { useState } from "react";
import {
  BadgeCheck,
  Building2,
  Check,
  CircleCheck,
  CircleX,
  Crosshair,
  IndianRupee,
  LoaderCircle,
  MessageSquareQuote,
  Save,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { API_BASE } from "../../lib/api";

const defaults = {
  business_name: "",
  services: "",
  proof_points: "",
  price_floor: 50000,
  list_price: 80000,
  discount_limit: 0.1,
  conversion_definition: "qualified_meeting",
  human_name: "",
  faq: "",
  faq_terms: "",
  ideal_clients: "",
  anti_ideal_clients: "",
  geographies: "india",
  languages: "en",
  guarantees: "",
  testimonials: "",
  calendar_link: "",
  timezone: "Asia/Kolkata",
  objection_price: "",
  objection_agency: "",
  objection_timing: "",
};

const lines = (value) => value.split("\n").map((s) => s.trim()).filter(Boolean);
const csv = (value) => value.split(",").map((s) => s.trim()).filter(Boolean);

function Section({ icon: Icon, title, description, children }) {
  return (
    <div className="form-section">
      <div className="form-section-head">
        <span className="stat-icon tone-accent" style={{ width: 34, height: 34, borderRadius: 9 }}>
          <Icon size={16} strokeWidth={2} />
        </span>
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {children}
    </div>
  );
}

export default function ProfileForm({ initial, approved }) {
  const [form, setForm] = useState({ ...defaults, ...initial });
  const [forReview, setForReview] = useState(false);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(null);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function save(event) {
    event.preventDefault();
    setLoading("save");
    setStatus(null);
    const objections = {};
    if (form.objection_price) objections.price = form.objection_price;
    if (form.objection_agency) objections.agency = form.objection_agency;
    if (form.objection_timing) objections.timing = form.objection_timing;
    const body = {
      business_name: form.business_name,
      services: lines(form.services),
      proof_points: lines(form.proof_points),
      price_floor: Number(form.price_floor),
      list_price: Number(form.list_price),
      discount_limit: Number(form.discount_limit),
      conversion_definition: form.conversion_definition,
      human_name: form.human_name,
      faq: lines(form.faq),
      faq_terms: csv(form.faq_terms),
      ideal_clients: lines(form.ideal_clients),
      anti_ideal_clients: lines(form.anti_ideal_clients),
      geographies: csv(form.geographies),
      languages: csv(form.languages),
      guarantees: lines(form.guarantees),
      testimonials: lines(form.testimonials),
      calendar_link: form.calendar_link,
      timezone: form.timezone,
      objections,
      version: 1,
      submit_for_review: forReview,
    };
    try {
      const response = await fetch(`${API_BASE}/acquisition/profile`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      setStatus(response.ok ? { type: "success", text: "Profile saved." } : { type: "error", text: `Save failed (${response.status})` });
    } catch {
      setStatus({ type: "error", text: "Cannot reach API." });
    }
    setLoading(null);
  }

  async function approve() {
    setLoading("approve");
    try {
      const response = await fetch(`${API_BASE}/acquisition/profile/approve`, { method: "POST" });
      setStatus(response.ok ? { type: "success", text: "Profile approved. Outreach is now enabled." } : { type: "error", text: `Approve failed (${response.status})` });
    } catch {
      setStatus({ type: "error", text: "Cannot reach API." });
    }
    setLoading(null);
  }

  return (
    <form onSubmit={save} className="form-grid">
      <Section icon={Building2} title="Business identity" description="Who the agents represent and who takes over after conversion.">
        <div className="grid grid-2">
          <div className="form-field">
            <label htmlFor="business_name">Business name</label>
            <input id="business_name" value={form.business_name} onChange={set("business_name")} placeholder="Northwind Analytics" required />
          </div>
          <div className="form-field">
            <label htmlFor="human_name">Handoff contact</label>
            <input id="human_name" value={form.human_name} onChange={set("human_name")} placeholder="Mina Shah" required />
          </div>
        </div>
        <div className="grid grid-3">
          <div className="form-field">
            <label htmlFor="geographies">Geographies</label>
            <input id="geographies" value={form.geographies} onChange={set("geographies")} placeholder="india, us" />
          </div>
          <div className="form-field">
            <label htmlFor="languages">Languages</label>
            <input id="languages" value={form.languages} onChange={set("languages")} placeholder="en, hi" />
          </div>
          <div className="form-field">
            <label htmlFor="timezone">Timezone</label>
            <input id="timezone" value={form.timezone} onChange={set("timezone")} placeholder="Asia/Kolkata" />
          </div>
        </div>
        <div className="form-field">
          <label htmlFor="calendar_link">Calendar link</label>
          <input id="calendar_link" value={form.calendar_link} onChange={set("calendar_link")} placeholder="https://cal.com/you/intro" />
        </div>
      </Section>

      <Section icon={Sparkles} title="Offer & proof" description="The critic blocks any number or claim that isn't written here.">
        <div className="grid grid-2">
          <div className="form-field">
            <label htmlFor="services">Services — one per line</label>
            <textarea id="services" value={form.services} onChange={set("services")} placeholder={"Checkout audit\nCart abandonment review"} rows={3} />
          </div>
          <div className="form-field">
            <label htmlFor="proof_points">Proof points — one per line</label>
            <textarea id="proof_points" value={form.proof_points} onChange={set("proof_points")} placeholder="A shop fixed shipping rates before account creation." rows={3} />
          </div>
        </div>
        <div className="grid grid-2">
          <div className="form-field">
            <label htmlFor="guarantees">Guarantees</label>
            <textarea id="guarantees" value={form.guarantees} onChange={set("guarantees")} rows={2} placeholder="Audit delivered in 5 business days." />
          </div>
          <div className="form-field">
            <label htmlFor="testimonials">Testimonials</label>
            <textarea id="testimonials" value={form.testimonials} onChange={set("testimonials")} rows={2} />
          </div>
        </div>
      </Section>

      <Section icon={Crosshair} title="Targeting" description="Seeds the ICP hypotheses and the fit score.">
        <div className="grid grid-2">
          <div className="form-field">
            <label htmlFor="ideal_clients">Ideal clients — one per line</label>
            <textarea id="ideal_clients" value={form.ideal_clients} onChange={set("ideal_clients")} rows={2} placeholder={"shopify\ndtc"} />
          </div>
          <div className="form-field">
            <label htmlFor="anti_ideal_clients">Anti-ideal clients — one per line</label>
            <textarea id="anti_ideal_clients" value={form.anti_ideal_clients} onChange={set("anti_ideal_clients")} rows={2} placeholder={"marketplace\naggregator"} />
          </div>
        </div>
      </Section>

      <Section icon={MessageSquareQuote} title="Objections & FAQ" description="Approved answers. Agents may adapt wording, never substance.">
        <div className="grid grid-3">
          <div className="form-field">
            <label htmlFor="objection_price">“Too expensive”</label>
            <textarea id="objection_price" value={form.objection_price} onChange={set("objection_price")} rows={3} />
          </div>
          <div className="form-field">
            <label htmlFor="objection_agency">“We already have an agency”</label>
            <textarea id="objection_agency" value={form.objection_agency} onChange={set("objection_agency")} rows={3} />
          </div>
          <div className="form-field">
            <label htmlFor="objection_timing">“Not the right time”</label>
            <textarea id="objection_timing" value={form.objection_timing} onChange={set("objection_timing")} rows={3} />
          </div>
        </div>
        <div className="grid grid-2">
          <div className="form-field">
            <label htmlFor="faq">FAQ answers — one per line</label>
            <textarea id="faq" value={form.faq} onChange={set("faq")} rows={2} />
          </div>
          <div className="form-field">
            <label htmlFor="faq_terms">FAQ keywords</label>
            <input id="faq_terms" value={form.faq_terms} onChange={set("faq_terms")} placeholder="audit, checkout" />
            <span className="form-hint">Comma-separated. Questions outside these escalate to you.</span>
          </div>
        </div>
      </Section>

      <Section icon={IndianRupee} title="Commercial terms" description="Hard limits. Agents can never go below the floor or exceed discount authority.">
        <div className="grid grid-3">
          <div className="form-field">
            <label htmlFor="price_floor">Price floor (₹)</label>
            <input id="price_floor" type="number" value={form.price_floor} onChange={set("price_floor")} />
          </div>
          <div className="form-field">
            <label htmlFor="list_price">List price (₹)</label>
            <input id="list_price" type="number" value={form.list_price} onChange={set("list_price")} />
          </div>
          <div className="form-field">
            <label htmlFor="discount_limit">Max discount (0–1)</label>
            <input id="discount_limit" type="number" step="0.01" min="0" max="1" value={form.discount_limit} onChange={set("discount_limit")} />
          </div>
        </div>
        <div className="form-field">
          <label htmlFor="conversion_definition">Conversion definition</label>
          <select id="conversion_definition" value={form.conversion_definition} onChange={set("conversion_definition")}>
            <option value="qualified_meeting">Qualified meeting booked</option>
            <option value="signed_proposal">Signed proposal</option>
            <option value="paid">Signed and paid</option>
          </select>
        </div>
      </Section>

      <Section icon={ShieldCheck} title="Publish" description="Nothing is sent until the profile is approved.">
        <label className="checkbox-field">
          <input type="checkbox" checked={forReview} onChange={(e) => setForReview(e.target.checked)} />
          <span>Submit for review instead of auto-approving. Outreach stays blocked until you approve.</span>
        </label>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading !== null}>
            {loading === "save" ? <LoaderCircle size={15} className="spin" /> : <Save size={15} />}
            {loading === "save" ? "Saving" : "Save profile"}
          </button>
          {!approved || forReview ? (
            <button type="button" className="btn btn-secondary" onClick={approve} disabled={loading !== null}>
              {loading === "approve" ? <LoaderCircle size={15} className="spin" /> : <BadgeCheck size={15} />}
              Approve profile
            </button>
          ) : (
            <span className="badge badge-success"><Check size={12} strokeWidth={2.6} />Approved</span>
          )}
        </div>
        {status ? (
          <div className={`toast toast-${status.type}`}>
            {status.type === "success" ? <CircleCheck size={15} /> : <CircleX size={15} />}
            {status.text}
          </div>
        ) : null}
      </Section>
    </form>
  );
}
