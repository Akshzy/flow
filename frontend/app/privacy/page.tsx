import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy | Floww",
  description:
    "How Floww collects, processes, stores, and uses information when you use the Floww service or connect supported third-party platforms.",
};

/**
 * Floww Privacy Policy (public route, no authentication required).
 *
 * Source of truth: FLOWW_PRIVACY_POLICY.md at the repository root. The
 * content below faithfully represents that policy, including all
 * [TO BE COMPLETED] placeholders. Placeholders are styled distinctly so
 * incomplete information is never mistaken for real contact details.
 */

function Placeholder() {
  return (
    <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-900">
      [TO BE COMPLETED]
    </span>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="mt-10 text-xl font-semibold tracking-tight text-slate-900">
        {title}
      </h2>
      <div className="mt-3 space-y-3 text-sm leading-6 text-slate-700">
        {children}
      </div>
    </section>
  );
}

function Bullets({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <p className="text-xs uppercase tracking-wide text-slate-500">
        <Link href="/" className="font-medium text-slate-900 underline">
          Floww
        </Link>{" "}
        / Privacy Policy
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
        Privacy Policy
      </h1>
      <p className="mt-1 text-sm text-slate-500">Last Updated: September 29, 2026</p>

      <div className="mt-6 space-y-3 text-sm leading-6 text-slate-700">
        <p>
          Floww (&ldquo;Floww&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;, or
          &ldquo;our&rdquo;) provides software that helps businesses organize
          and manage customer orders and business communications received
          through supported messaging platforms.
        </p>
        <p>
          This Privacy Policy explains what information Floww may collect,
          receive, process, store, and use when you use the Floww service or
          connect supported third-party platforms such as Meta services.
        </p>
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <strong>IMPORTANT:</strong> Floww may process information contained
          in customer conversations because businesses may connect messaging
          platforms to Floww for the purpose of organizing customer inquiries
          and orders.
        </p>
      </div>

      <Section id="who-we-are" title="1. Who We Are">
        <p>Floww is operated by:</p>
        <ul className="list-none space-y-1 pl-0">
          <li>
            <strong>Legal/Business Name:</strong> <Placeholder />
          </li>
          <li>
            <strong>Contact Email:</strong> <Placeholder />
          </li>
          <li>
            <strong>Website:</strong> <Placeholder />
          </li>
        </ul>
        <p>Do not replace these placeholders with invented information.</p>
      </Section>

      <Section id="information-we-process" title="2. Information We Process">
        <p>
          Depending on how Floww is used, we may process the following
          categories of information.
        </p>

        <h3 className="pt-2 text-base font-semibold text-slate-900">
          2.1 Account Information
        </h3>
        <p>
          When you create a Floww account, we may process information such as:
        </p>
        <Bullets
          items={[
            "name",
            "email address",
            "authentication information",
            "account identifiers",
            "account and tenant membership information",
          ]}
        />

        <h3 className="pt-2 text-base font-semibold text-slate-900">
          2.2 Business Information
        </h3>
        <p>If you use Floww for a business, we may process:</p>
        <Bullets
          items={[
            "business name",
            "business/tenant identifiers",
            "user membership and role information",
            "connected platform identifiers",
            "configuration information required to operate the service",
          ]}
        />

        <h3 className="pt-2 text-base font-semibold text-slate-900">
          2.3 Messaging and Customer Information
        </h3>
        <p>
          When a business connects a supported messaging platform to Floww,
          Floww may process information contained in messages and related
          platform events, including:
        </p>
        <Bullets
          items={[
            "message content",
            "message timestamps",
            "sender/recipient identifiers",
            "customer names where provided",
            "customer contact information where provided",
            "conversation identifiers",
            "platform-specific identifiers",
            "information contained in customer order requests",
          ]}
        />
        <p>
          The exact information processed depends on the platform and
          permissions authorized by the business.
        </p>

        <h3 className="pt-2 text-base font-semibold text-slate-900">
          2.4 Order Information
        </h3>
        <p>
          Floww may process structured information derived from customer
          conversations, including:
        </p>
        <Bullets
          items={[
            "products or services requested",
            "quantities",
            "customer-provided delivery information",
            "customer-provided contact information",
            "order status",
            "order timestamps",
            "corrections or confirmations made by the business",
          ]}
        />

        <h3 className="pt-2 text-base font-semibold text-slate-900">
          2.5 Technical and Security Information
        </h3>
        <p>
          We may process technical information necessary to operate and secure
          Floww, including:
        </p>
        <Bullets
          items={[
            "IP address",
            "request identifiers",
            "authentication/session metadata",
            "security and audit records",
            "application error information",
            "API and integration metadata",
          ]}
        />
        <p>
          We use such information for security, reliability, debugging,
          fraud/abuse prevention, and service operation.
        </p>
      </Section>

      <Section id="how-we-use-information" title="3. How We Use Information">
        <p>We process information for purposes including:</p>
        <Bullets
          items={[
            "providing the Floww service",
            "authenticating users",
            "managing business accounts and memberships",
            "connecting authorized third-party platforms",
            "receiving and organizing business messages",
            "converting eligible customer requests into structured order data",
            "allowing businesses to review and manage extracted order information",
            "providing exports and other requested business functionality",
            "maintaining audit and security records",
            "detecting and preventing abuse",
            "diagnosing technical problems",
            "maintaining and improving the reliability of the service",
            "complying with applicable legal obligations",
          ]}
        />
        <p>
          Floww does not use customer conversation data for purposes unrelated
          to the service unless separately disclosed and legally permitted.
        </p>
      </Section>

      <Section id="ai-processing" title="4. AI Processing">
        <p>
          Some Floww functionality may use automated or artificial
          intelligence systems to analyze customer messages and identify
          structured order information.
        </p>
        <p>For example, Floww may process a customer message to identify:</p>
        <Bullets
          items={[
            "product",
            "quantity",
            "customer-provided information",
            "delivery information",
            "other order-related fields",
          ]}
        />
        <p>
          AI-generated information is treated as an extraction or candidate
          result and may require business review before becoming an
          authoritative order record.
        </p>
        <p>
          Floww does not intentionally treat an AI-generated result as
          authoritative merely because an AI system produced it.
        </p>
      </Section>

      <Section
        id="third-party-platform-integrations"
        title="5. Third-Party Platform Integrations"
      >
        <p>
          Floww may integrate with third-party services and platforms,
          including Meta products such as WhatsApp and Instagram, where
          supported and authorized by the business.
        </p>
        <p>When a business connects a third-party platform:</p>
        <Bullets
          items={[
            "the business authorizes the relevant integration;",
            "Floww processes information made available through the authorized integration;",
            "Floww does not request or collect the business user's third-party account password;",
            "platform data is processed according to the applicable platform permissions, terms, and policies.",
          ]}
        />
        <p>Third-party platforms have their own privacy policies and terms.</p>
      </Section>

      <Section id="meta-platform-data" title="6. Meta Platform Data">
        <p>
          Where Floww uses Meta platform functionality, Floww may process data
          made available through the permissions and integrations authorized
          by the relevant business.
        </p>
        <p>
          Such information may include business identifiers, platform
          identifiers, phone-number identifiers, messages, conversation data,
          and other information necessary to provide the connected
          functionality.
        </p>
        <p>
          Floww will use Meta platform data only for purposes permitted by the
          applicable Meta policies, permissions, and the Floww service.
        </p>
      </Section>

      <Section id="data-sharing" title="7. Data Sharing">
        <p>
          We may disclose information to service providers that help us
          operate Floww, such as infrastructure, hosting, database, security,
          monitoring, and other technology providers, where necessary to
          provide the service.
        </p>
        <p>
          Service providers are expected to process information only for the
          purposes for which they are engaged and subject to appropriate
          contractual and security controls.
        </p>
        <p>
          We may also disclose information where required by applicable law,
          legal process, or to protect the rights, safety, security, and
          integrity of Floww, its users, or others.
        </p>
        <p>
          Floww does not sell customer conversation data or Meta platform
          data.
        </p>
      </Section>

      <Section id="data-retention" title="8. Data Retention">
        <p>
          We retain information for as long as reasonably necessary to provide
          the service, maintain security and audit records, comply with legal
          obligations, resolve disputes, and enforce agreements.
        </p>
        <p>
          Retention periods may vary depending on the type of information and
          the purpose for which it is processed.
        </p>
        <p>
          When information is no longer required, Floww will delete it or
          appropriately de-identify it, subject to applicable legal, security,
          backup, and operational requirements.
        </p>
      </Section>

      <Section id="data-deletion" title="9. Data Deletion">
        <p>
          Users may request deletion of information associated with their
          Floww account or information processed by Floww on their behalf.
        </p>
        <p>Deletion requests can be submitted through:</p>
        <p>
          Email: <Placeholder />
        </p>
        <p>Subject: Floww Data Deletion Request</p>
        <p>
          Please include enough information for us to identify the relevant
          account or business connection.
        </p>
        <p>
          Where applicable, disconnecting a third-party platform may also stop
          future data from that integration from being received by Floww.
        </p>
        <p>
          Some information may be retained where required by law, necessary
          for security, fraud prevention, dispute resolution, or legitimate
          backup and operational requirements.
        </p>
        <p>
          Where Meta or another platform requires deletion of platform data,
          Floww will follow the applicable platform requirements.
        </p>
      </Section>

      <Section id="data-security" title="10. Data Security">
        <p>
          We use reasonable technical and organizational safeguards designed
          to protect information against unauthorized access, alteration,
          disclosure, loss, or destruction.
        </p>
        <p>Security measures may include:</p>
        <Bullets
          items={[
            "authentication and authorization controls",
            "tenant isolation",
            "access controls",
            "encrypted transport",
            "protected secret management",
            "audit logging",
            "security monitoring",
            "database access controls",
          ]}
        />
        <p>No internet-based service can guarantee absolute security.</p>
      </Section>

      <Section id="multi-tenant-isolation" title="11. Multi-Tenant Isolation">
        <p>Floww is designed as a multi-tenant service.</p>
        <p>
          Business data is associated with a specific business/tenant and
          access is controlled through authentication and authorization
          mechanisms.
        </p>
        <p>
          Users are not authorized to access another business&apos;s
          information merely by knowing or submitting an object identifier.
        </p>
      </Section>

      <Section id="children" title="12. Children">
        <p>
          Floww is intended for businesses and is not directed toward
          children.
        </p>
        <p>
          We do not knowingly design the service to collect personal
          information from children for the purpose of providing the Floww
          service.
        </p>
      </Section>

      <Section id="international-processing" title="13. International Processing">
        <p>
          Depending on the infrastructure and service providers used by Floww,
          information may be processed in countries other than the country in
          which the user or business is located.
        </p>
        <p>
          Where applicable, Floww will use appropriate safeguards required by
          applicable law.
        </p>
      </Section>

      <Section id="your-rights" title="14. Your Rights">
        <p>
          Depending on applicable law, users may have rights concerning their
          personal information, including rights to:
        </p>
        <Bullets
          items={[
            "request access",
            "request correction",
            "request deletion",
            "request information about processing",
            "object to or restrict certain processing",
            "exercise other rights provided by applicable law",
          ]}
        />
        <p>Requests can be submitted using the contact information below.</p>
      </Section>

      <Section id="changes-to-this-policy" title="15. Changes to This Policy">
        <p>
          We may update this Privacy Policy when the Floww service,
          integrations, data practices, or applicable legal requirements
          change.
        </p>
        <p>
          The &ldquo;Last Updated&rdquo; date at the top of this policy will
          be updated when material changes are made.
        </p>
      </Section>

      <Section id="contact" title="16. Contact">
        <p>Privacy Contact:</p>
        <ul className="list-none space-y-1 pl-0">
          <li>
            <strong>Legal/Business Name:</strong> <Placeholder />
          </li>
          <li>
            <strong>Email:</strong> <Placeholder />
          </li>
          <li>
            <strong>Website:</strong> <Placeholder />
          </li>
        </ul>
        <p>
          For data deletion requests, use the subject:{" "}
          <span className="font-medium">&ldquo;Floww Data Deletion
          Request&rdquo;</span>
        </p>
      </Section>

      <Section
        id="meta-platform-requirements"
        title="17. Meta Platform Requirements"
      >
        <p>
          Where Floww uses Meta platform functionality, Floww will maintain
          appropriate disclosures concerning the information it processes and
          will provide users with an accessible mechanism to request deletion
          of applicable information.
        </p>
        <p>
          This Privacy Policy does not grant Floww rights beyond those
          permitted by applicable law, Meta policies, platform permissions, or
          other applicable agreements.
        </p>
      </Section>
    </main>
  );
}
