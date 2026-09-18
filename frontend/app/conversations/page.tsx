import { ModuleRoadmap } from "@/components/ModuleRoadmap";

export default function ConversationsPage() {
  return (
    <ModuleRoadmap
      title="Conversations"
      description="Threaded prospect conversations with full history feeding the handover dossier"
      module="Conversations"
      foundation={[
        "conversations + conversation_messages tables (immutable message history)",
        "Inbound reply capture with verbatim content + metadata",
        "Dossier endpoint (/handover/{ticket}/dossier) with full history + outreach count",
        "Deterministic intent/sentiment classification on every reply",
      ]}
      planned={[
        "Threaded conversation UI per ticket with outgoing message composer",
        "Reply-detection integration with email providers (IMAP/API)",
        "AI-assisted reply suggestions (Handover AI)",
        "Transcript search + keyword alerts",
      ]}
    />
  );
}
