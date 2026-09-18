import { ModuleRoadmap } from "@/components/ModuleRoadmap";

export default function OutreachPage() {
  return (
    <ModuleRoadmap
      title="Outreach"
      description="Compliant, suppression-checked automated outreach with automatic stop on reply"
      module="Outreach"
      foundation={[
        "Suppression/DO-NOT-CONTACT registry — checked before any send (enforced in code + tested)",
        "Reply webhook with HMAC signature verification (live-verified)",
        "Handover rule: reply → automation paused → status REPLIED/HOT_LEAD → owner notified (tested end-to-end)",
        "Conversation history + verbatim message recording",
        "Outreach AI agent registered (draft/schedule tools, suppression-check mandatory)",
      ]}
      planned={[
        "Campaign + sequence designer (outreach_campaigns / outreach_sequences tables defined in roadmap)",
        "Provider send adapters (email/SMS) with quiet hours from system_settings",
        "A/B templates + send analytics",
        "Explicit re-authorization flow to resume automation after handover",
      ]}
    />
  );
}
