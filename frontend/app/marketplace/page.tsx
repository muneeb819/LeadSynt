import { ModuleRoadmap } from "@/components/ModuleRoadmap";

export default function MarketplacePage() {
  return (
    <ModuleRoadmap
      title="Marketplace"
      description="Domain-specific opportunity browsing: real estate, vehicles, aircraft, yachts, collectibles, art, hospitality, travel, businesses, procurement, jobs, RFP/RFQ"
      module="Marketplace"
      foundation={[
        "Marketplace domains stored on ticket categories (marketplace_domain field)",
        "CONNECTOR framework for authorized marketplace sources (dev_feed proves the pipeline)",
        "Entity resolution + dedup for listings across sources",
        "Verification + provenance mandatory per listing",
      ]}
      planned={[
        "Domain-specific listing views with filters (real estate, vehicles, aircraft…)",
        "Approved marketplace source connectors (APIs / licensed feeds only)",
        "Buyer/seller matching signals",
        "Market Intelligence AI context per domain",
      ]}
    />
  );
}
