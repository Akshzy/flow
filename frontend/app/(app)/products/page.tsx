"use client";

import { EmptyState, PageHeader } from "@/components/ui";

/** Products (Phase 10): NO product/catalog API exists yet — no fake CRUD is
 * built. This page documents the future catalog capability honestly. */
export default function ProductsPage() {
  return (
    <>
      <PageHeader title="Products" description="Your product catalog." />
      <EmptyState
        message="The product catalog is not available yet."
        hint="Products are not yet managed by Floww. Extracted order items reference product names from customer messages; a dedicated catalog capability is planned for a future phase."
      />
    </>
  );
}
