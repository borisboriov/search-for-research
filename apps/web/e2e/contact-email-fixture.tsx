// Playwright-only entry: never imported by Next or added to the catalogue.
import { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { ContactCard } from "../components/contact-card";
import { observeProfile, whenVisible } from "../lib/analytics";
import type { SupervisorCard } from "../lib/types";

const card: SupervisorCard = {
  author_id: "synthetic-contact-fixture", name: "Synthetic email fixture",
  email: "researcher@example.invalid", institution: null, h_index: null,
  works_count: null, topics: [], profile_text: "", cited_by_count: null,
  position: null, top_works: [], serendipity: false,
};
function Fixture() {
  useEffect(() => whenVisible(() => { void observeProfile(card.author_id); }), []);
  return <><h1>Synthetic contact component fixture</h1><ContactCard card={card} /></>;
}
createRoot(document.getElementById("fixture")!).render(<Fixture />);
