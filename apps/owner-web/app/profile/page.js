import { Building2, Handshake, IndianRupee, UserRound } from "lucide-react";
import Alert from "../../components/Alert";
import Badge from "../../components/Badge";
import PageHeader from "../../components/PageHeader";
import StatCard from "../../components/StatCard";
import ProfileForm from "./ProfileForm";
import { apiGet } from "../../lib/api";

export default async function ProfilePage() {
  const data = await apiGet("/acquisition/profile");

  if (data.error && data.status === 404) {
    return (
      <>
        <PageHeader
          title="Service profile"
          description="The only human input. Every claim the agents make must trace back to this profile."
        />
        <Alert variant="info">No profile yet. Complete the form below to onboard — outreach stays blocked until it is approved.</Alert>
        <ProfileForm initial={{}} approved={false} />
      </>
    );
  }

  if (data.error) {
    return (
      <>
        <PageHeader title="Service profile" />
        <Alert variant="error">{data.error}</Alert>
      </>
    );
  }

  const objections = data.objections || {};
  const initial = {
    business_name: data.business_name,
    services: (data.services || []).join("\n"),
    proof_points: (data.proof_points || []).join("\n"),
    price_floor: data.price_floor,
    list_price: data.list_price,
    discount_limit: data.discount_limit,
    conversion_definition: data.conversion_definition,
    human_name: data.human_name,
    faq: (data.faq || []).join("\n"),
    faq_terms: (data.faq_terms || []).join(", "),
    ideal_clients: (data.ideal_clients || []).join("\n"),
    anti_ideal_clients: (data.anti_ideal_clients || []).join("\n"),
    geographies: (data.geographies || ["india"]).join(", "),
    languages: (data.languages || ["en"]).join(", "),
    guarantees: (data.guarantees || []).join("\n"),
    testimonials: (data.testimonials || []).join("\n"),
    calendar_link: data.calendar_link || "",
    timezone: data.timezone || "Asia/Kolkata",
    objection_price: objections.price || "",
    objection_agency: objections.agency || "",
    objection_timing: objections.timing || "",
  };

  return (
    <>
      <PageHeader
        title="Service profile"
        description="The only human input. Every claim the agents make must trace back to this profile — keep proof points factual."
      >
        <Badge variant={data.approved ? "success" : "warning"} dot>
          {data.approved ? `Approved · v${data.version ?? 1}` : "Pending approval"}
        </Badge>
      </PageHeader>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard icon={Building2} tone="accent" label="Business" value={<span style={{ fontSize: 18 }}>{data.business_name}</span>} hint={`${(data.services || []).length} services`} />
        <StatCard icon={Handshake} tone="success" label="Converts on" value={<span style={{ fontSize: 18, textTransform: "capitalize" }}>{data.conversion_definition?.replace(/_/g, " ")}</span>} />
        <StatCard icon={UserRound} tone="info" label="Handoff to" value={<span style={{ fontSize: 18 }}>{data.human_name}</span>} />
        <StatCard icon={IndianRupee} tone="warning" label="Price floor" value={<span style={{ fontSize: 18 }}>₹{Number(data.price_floor).toLocaleString("en-IN")}</span>} hint={`Max discount ${Math.round((data.discount_limit || 0) * 100)}%`} />
      </div>

      <ProfileForm initial={initial} approved={data.approved} />
    </>
  );
}
