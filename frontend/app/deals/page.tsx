import { ModuleRoadmap } from "@/components/ModuleRoadmap";

export default function DealsPage() {
  return (
    <ModuleRoadmap
      title="Deals"
      description="Deal stage tracking from negotiation through won/lost, with events and value"
      module="Deals"
      foundation={[
        "Status machine covers the deal zone: MEETING_BOOKED → NEGOTIATION → PROPOSAL_SENT → WON/LOST (valid transitions only)",
        "Budget / currency / deal size on every ticket",
        "Dashboard KPIs: open deals, won deals (live)",
        "Deal events flow through the audit trail + event bus (deal.created / deal.updated names reserved)",
      ]}
      planned={[
        "deals / deal_stages / deal_events tables (in the full schema roadmap)",
        "Pipeline value forecasting + win-rate analytics",
        "Stage-gated reminders + meeting/appointment scheduling",
        "Proposal document generation",
      ]}
    />
  );
}
