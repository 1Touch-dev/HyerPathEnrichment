"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/providers/auth-provider";
import { parseResponseEnvelopeError, unwrapEnvelopeData } from "@/src/lib/api-envelope";
import {
  parseBrandLandingConfig,
  RESERVED_KEYS,
  serializeBrandLandingConfig,
  type BrandLandingCopy,
  type ParsedBrandLandingConfig,
} from "@/src/lib/brand-landing-config";
import { hasPermission } from "@/src/lib/product-doors";
import type { AdminBrand, AdminBrandCreate, AdminBrandUpdate } from "@/src/lib/types";

const SLUG_PATTERN = /^[a-z0-9-]+$/;

const TIERS_FIXTURE_WARNING =
  "This JSON uses a reserved `tiers` key, so public tier URLs will 404. Saving overwrites it with a slug-keyed map.";

type LandingTierRow = {
  slug: string;
  headline: string;
  ctaLabel: string;
};

const EMPTY_TIER_ROW: LandingTierRow = { slug: "", headline: "", ctaLabel: "" };

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Reserved `tiers` key 404s every public tier URL — warn before save. */
function looksLikeTiersFixture(value: unknown): boolean {
  return isPlainObject(value) && "tiers" in value;
}

type JsonFieldResult =
  { ok: true; value: Record<string, unknown> | null | undefined } | { ok: false; error: string };

function parseJsonObjectField(raw: string, previousHadValue: boolean): JsonFieldResult {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { ok: true, value: previousHadValue ? null : undefined };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return { ok: false, error: "Invalid JSON" };
  }
  if (parsed === null) {
    return { ok: true, value: previousHadValue ? null : undefined };
  }
  if (!isPlainObject(parsed)) {
    return { ok: false, error: "JSON must be an object" };
  }
  return { ok: true, value: parsed };
}

function stringifyConfig(value: Record<string, unknown> | null): string {
  return value ? JSON.stringify(value, null, 2) : "";
}

function parsedLandingToRows(parsed: ParsedBrandLandingConfig): LandingTierRow[] {
  return Object.entries(parsed.tiers).map(([slug, copy]) => ({
    slug,
    headline: copy.headline ?? "",
    ctaLabel: copy.ctaLabel ?? "",
  }));
}

function formToParsedLanding(
  generalHeadline: string,
  generalCta: string,
  rows: LandingTierRow[],
): { ok: true; parsed: ParsedBrandLandingConfig } | { ok: false; error: string } {
  const headline = generalHeadline.trim();
  const ctaLabel = generalCta.trim();
  const generalCopy: BrandLandingCopy | null =
    headline || ctaLabel
      ? {
          ...(headline ? { headline } : {}),
          ...(ctaLabel ? { ctaLabel } : {}),
        }
      : null;

  const tiers: Record<string, BrandLandingCopy> = {};
  for (const row of rows) {
    const slug = row.slug.trim();
    const rowHeadline = row.headline.trim();
    const rowCta = row.ctaLabel.trim();
    if (!slug && !rowHeadline && !rowCta) continue;
    if (!slug) {
      return { ok: false, error: "Landing page: tier slug is required" };
    }
    if (slug in tiers) {
      return { ok: false, error: `Landing page: duplicate tier slug "${slug}"` };
    }
    if (!rowHeadline && !rowCta) {
      return { ok: false, error: `Landing page: tier "${slug}" needs a headline or CTA` };
    }
    tiers[slug] = {
      ...(rowHeadline ? { headline: rowHeadline } : {}),
      ...(rowCta ? { ctaLabel: rowCta } : {}),
    };
  }

  return { ok: true, parsed: { generalCopy, tiers } };
}

async function readBrandResponse(res: Response): Promise<AdminBrand> {
  if (!res.ok) throw await parseResponseEnvelopeError(res);
  const json: unknown = await res.json();
  return unwrapEnvelopeData<AdminBrand>(json);
}

export default function AdminBrandsPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const canWriteBrands = hasPermission(user, { resource: "brands", action: "write" });
  const canDeleteBrands = hasPermission(user, { resource: "brands", action: "delete" });

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-brands"],
    queryFn: async () => {
      const res = await fetch("/api/admin/brands");
      if (!res.ok) throw await parseResponseEnvelopeError(res);
      const json: unknown = await res.json();
      return unwrapEnvelopeData<AdminBrand[]>(json);
    },
  });
  const brands = data ?? [];

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminBrand | null>(null);
  const [deactivating, setDeactivating] = useState<AdminBrand | null>(null);

  const createMutation = useMutation({
    mutationFn: async (payload: AdminBrandCreate) => {
      const res = await fetch("/api/admin/brands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return readBrandResponse(res);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      setCreateOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ brandId, payload }: { brandId: string; payload: AdminBrandUpdate }) => {
      const res = await fetch(`/api/admin/brands/${brandId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return readBrandResponse(res);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      setEditing(null);
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async ({ brandId, reason }: { brandId: string; reason?: string }) => {
      const res = await fetch(`/api/admin/brands/${brandId}/deactivate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reason ? { reason } : {}),
      });
      return readBrandResponse(res);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      setDeactivating(null);
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: async (brandId: string) => {
      const res = await fetch(`/api/admin/brands/${brandId}/reactivate`, {
        method: "POST",
      });
      return readBrandResponse(res);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
    },
  });

  if (isLoading && !data) {
    return <p className="text-sm text-muted-foreground">Loading brands…</p>;
  }

  if (error) {
    return (
      <p className="text-sm text-destructive">
        {error instanceof Error ? error.message : "Failed to load brands"}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Brands</h1>
        {canWriteBrands ? (
          <Button
            onClick={() => {
              createMutation.reset();
              setCreateOpen(true);
            }}
          >
            Create brand
          </Button>
        ) : null}
      </div>
      {!brands.length ? (
        <EmptyState
          title="No brands yet"
          description={
            canWriteBrands
              ? "Create a brand to publish a landing page and manage its config."
              : "Brands available to your account will appear here."
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {brands.map((brand) => (
            <Card key={brand.id}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  {brand.name}
                  <Badge variant={brand.isActive ? "success" : "outline"}>
                    {brand.isActive ? "Active" : "Inactive"}
                  </Badge>
                </CardTitle>
                <p className="text-sm text-muted-foreground">/{brand.slug}</p>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {brand.customDomain ? (
                  <p className="text-sm text-muted-foreground">{brand.customDomain}</p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Created {new Date(brand.createdAt).toLocaleString()}
                </p>
                <div className="flex flex-wrap gap-2">
                  {canWriteBrands ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        updateMutation.reset();
                        setEditing(brand);
                      }}
                    >
                      Edit
                    </Button>
                  ) : null}
                  {brand.isActive ? (
                    <Button asChild size="sm" variant="outline">
                      <a href={`/b/${brand.slug}`} target="_blank" rel="noreferrer">
                        View landing page
                      </a>
                    </Button>
                  ) : null}
                  {canDeleteBrands && brand.isActive ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        deactivateMutation.reset();
                        setDeactivating(brand);
                      }}
                    >
                      Deactivate
                    </Button>
                  ) : null}
                  {canDeleteBrands && !brand.isActive ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reactivateMutation.isPending}
                      onClick={() => reactivateMutation.mutate(brand.id)}
                    >
                      {reactivateMutation.isPending ? "Reactivating..." : "Reactivate"}
                    </Button>
                  ) : null}
                </div>
                {reactivateMutation.isError && reactivateMutation.variables === brand.id ? (
                  <p className="text-sm text-destructive">
                    {reactivateMutation.error instanceof Error
                      ? reactivateMutation.error.message
                      : "Reactivate failed"}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {canWriteBrands ? (
        <>
          <BrandFormDialog
            mode="create"
            open={createOpen}
            isPending={createMutation.isPending}
            submitError={
              createMutation.error instanceof Error ? createMutation.error.message : null
            }
            onOpenChange={(open) => {
              if (!open) createMutation.reset();
              setCreateOpen(open);
            }}
            onSubmit={(payload) => createMutation.mutate(payload as AdminBrandCreate)}
          />

          <BrandFormDialog
            mode="edit"
            brand={editing}
            open={editing !== null}
            isPending={updateMutation.isPending}
            submitError={
              updateMutation.error instanceof Error ? updateMutation.error.message : null
            }
            onOpenChange={(open) => {
              if (!open) {
                updateMutation.reset();
                setEditing(null);
              }
            }}
            onSubmit={(payload) => {
              if (!editing) return;
              updateMutation.mutate({ brandId: editing.id, payload });
            }}
          />
        </>
      ) : null}

      {canDeleteBrands ? (
        <DeactivateBrandDialog
          brand={deactivating}
          open={deactivating !== null}
          isPending={deactivateMutation.isPending}
          submitError={
            deactivateMutation.error instanceof Error ? deactivateMutation.error.message : null
          }
          onOpenChange={(open) => {
            if (!open) {
              deactivateMutation.reset();
              setDeactivating(null);
            }
          }}
          onConfirm={(reason) => {
            if (!deactivating) return;
            deactivateMutation.mutate({
              brandId: deactivating.id,
              reason: reason || undefined,
            });
          }}
        />
      ) : null}
    </div>
  );
}

interface BrandFormDialogProps {
  mode: "create" | "edit";
  brand?: AdminBrand | null;
  open: boolean;
  isPending?: boolean;
  submitError?: string | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: AdminBrandCreate | AdminBrandUpdate) => void;
}

function BrandFormDialog({
  mode,
  brand = null,
  open,
  isPending = false,
  submitError = null,
  onOpenChange,
  onSubmit,
}: BrandFormDialogProps) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [customDomain, setCustomDomain] = useState("");
  const [chatbotConfigText, setChatbotConfigText] = useState("");
  const [landingHeadline, setLandingHeadline] = useState("");
  const [landingCta, setLandingCta] = useState("");
  const [landingTiers, setLandingTiers] = useState<LandingTierRow[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [landingWarning, setLandingWarning] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const source = mode === "edit" ? brand : null;
    setName(source?.name ?? "");
    setSlug(source?.slug ?? "");
    setCustomDomain(source?.customDomain ?? "");
    setChatbotConfigText(stringifyConfig(source?.chatbotConfig ?? null));
    const parsed = parseBrandLandingConfig(source?.landingPageTierConfig ?? null);
    setLandingHeadline(parsed.generalCopy?.headline ?? "");
    setLandingCta(parsed.generalCopy?.ctaLabel ?? "");
    setLandingTiers(parsedLandingToRows(parsed));
    setFormError(null);
    setLandingWarning(
      source?.landingPageTierConfig && looksLikeTiersFixture(source.landingPageTierConfig)
        ? TIERS_FIXTURE_WARNING
        : null,
    );
  }, [open, mode, brand]);

  function handleOpenChange(next: boolean) {
    onOpenChange(next);
  }

  function updateLandingTier(index: number, patch: Partial<LandingTierRow>) {
    setLandingTiers((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function handleConfirm() {
    setFormError(null);
    const trimmedName = name.trim();
    const trimmedSlug = slug.trim();
    if (!trimmedName) {
      setFormError("Name is required");
      return;
    }
    if (!SLUG_PATTERN.test(trimmedSlug)) {
      setFormError("Slug must match ^[a-z0-9-]+$");
      return;
    }

    const previousChatbot = Boolean(brand?.chatbotConfig);
    const previousLanding = Boolean(brand?.landingPageTierConfig);
    const previousDomain = Boolean(brand?.customDomain);

    const chatbot = parseJsonObjectField(chatbotConfigText, previousChatbot);
    if (!chatbot.ok) {
      setFormError(`Chatbot config: ${chatbot.error}`);
      return;
    }

    const landingForm = formToParsedLanding(landingHeadline, landingCta, landingTiers);
    if (!landingForm.ok) {
      setFormError(landingForm.error);
      return;
    }
    const landing = serializeBrandLandingConfig(landingForm.parsed, {
      previousWasObject: previousLanding,
      isCreate: mode === "create",
    });
    if (!landing.ok) {
      setFormError(`Landing page tier config: ${landing.error}`);
      return;
    }

    const payload: AdminBrandCreate | AdminBrandUpdate = {
      name: trimmedName,
      slug: trimmedSlug,
    };

    const trimmedDomain = customDomain.trim();
    if (trimmedDomain) {
      payload.customDomain = trimmedDomain;
    } else if (mode === "edit" && previousDomain) {
      payload.customDomain = null;
    }

    if (chatbot.value !== undefined) {
      payload.chatbotConfig = chatbot.value;
    }
    if (landing.value !== undefined) {
      payload.landingPageTierConfig = landing.value;
    }

    onSubmit(payload);
  }

  const slugInvalid = slug.trim().length > 0 && !SLUG_PATTERN.test(slug.trim());
  const landingTierSlugInvalid = landingTiers.some((row) => {
    const rowSlug = row.slug.trim();
    const rowHeadline = row.headline.trim();
    const rowCta = row.ctaLabel.trim();
    if (!rowSlug && !rowHeadline && !rowCta) return false;
    return !SLUG_PATTERN.test(rowSlug) || RESERVED_KEYS.has(rowSlug);
  });
  const canSubmit =
    name.trim().length > 0 && SLUG_PATTERN.test(slug.trim()) && !landingTierSlugInvalid;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Create brand" : "Edit brand"}</DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Required name and slug. Chatbot config is optional JSON. Landing copy uses headline, CTA, and per-tier fields."
              : "Updates the write allowlist only. Status is changed with Deactivate / Reactivate."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="brand-name">Name</Label>
          <Input
            id="brand-name"
            placeholder="Acme Staffing"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="brand-slug">Slug</Label>
          <Input
            id="brand-slug"
            placeholder="acme-staffing"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            aria-invalid={slugInvalid}
          />
          {slugInvalid ? (
            <p className="text-sm text-destructive">Slug must match ^[a-z0-9-]+$</p>
          ) : (
            <p className="text-xs text-muted-foreground">Lowercase letters, digits, and hyphens.</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="brand-custom-domain">Custom domain</Label>
          <Input
            id="brand-custom-domain"
            placeholder="careers.example.com"
            value={customDomain}
            onChange={(e) => setCustomDomain(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="brand-chatbot-config">Chatbot config</Label>
          <Textarea
            id="brand-chatbot-config"
            className="font-mono text-xs"
            rows={5}
            placeholder="{}"
            value={chatbotConfigText}
            onChange={(e) => setChatbotConfigText(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Admin-only JSON object. Not shown on the public landing page.
          </p>
        </div>

        <div className="space-y-2">
          <Label>Landing page copy</Label>
          <div className="space-y-2">
            <Label htmlFor="landing-general-headline" className="text-xs text-muted-foreground">
              Headline
            </Label>
            <Input
              id="landing-general-headline"
              placeholder="Join Acme"
              value={landingHeadline}
              onChange={(e) => setLandingHeadline(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="landing-general-cta" className="text-xs text-muted-foreground">
              CTA label
            </Label>
            <Input
              id="landing-general-cta"
              placeholder="Get started"
              value={landingCta}
              onChange={(e) => setLandingCta(e.target.value)}
            />
          </div>
          {landingTiers.map((row, index) => {
            const trimmedTierSlug = row.slug.trim();
            const tierSlugInvalid =
              trimmedTierSlug.length > 0 &&
              (!SLUG_PATTERN.test(trimmedTierSlug) || RESERVED_KEYS.has(trimmedTierSlug));
            return (
              <div key={index} className="space-y-2 rounded-md border p-3">
                <div className="flex items-center justify-between gap-2">
                  <Label
                    htmlFor={`landing-tier-${index}-slug`}
                    className="text-xs text-muted-foreground"
                  >
                    Tier
                  </Label>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setLandingTiers((rows) => rows.filter((_, i) => i !== index))}
                  >
                    Remove
                  </Button>
                </div>
                <Input
                  id={`landing-tier-${index}-slug`}
                  placeholder="free"
                  value={row.slug}
                  onChange={(e) => updateLandingTier(index, { slug: e.target.value })}
                  aria-invalid={tierSlugInvalid}
                />
                {tierSlugInvalid ? (
                  <p className="text-sm text-destructive">
                    {RESERVED_KEYS.has(trimmedTierSlug)
                      ? `"${trimmedTierSlug}" is reserved and cannot be a tier slug`
                      : "Tier slug must match ^[a-z0-9-]+$"}
                  </p>
                ) : null}
                <Input
                  id={`landing-tier-${index}-headline`}
                  placeholder="Headline"
                  value={row.headline}
                  onChange={(e) => updateLandingTier(index, { headline: e.target.value })}
                />
                <Input
                  id={`landing-tier-${index}-cta`}
                  placeholder="CTA label"
                  value={row.ctaLabel}
                  onChange={(e) => updateLandingTier(index, { ctaLabel: e.target.value })}
                />
              </div>
            );
          })}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setLandingTiers((rows) => [...rows, { ...EMPTY_TIER_ROW }])}
          >
            Add tier
          </Button>
          {landingWarning ? (
            <p className="text-sm text-amber-600 dark:text-amber-400">{landingWarning}</p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Optional general and per-tier headline / CTA. Empty omits the field on create.
            </p>
          )}
        </div>

        {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
        {submitError ? <p className="text-sm text-destructive">{submitError}</p> : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isPending || !canSubmit}>
            {isPending ? "Saving..." : mode === "create" ? "Create brand" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface DeactivateBrandDialogProps {
  brand: AdminBrand | null;
  open: boolean;
  isPending?: boolean;
  submitError?: string | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (reason: string) => void;
}

function DeactivateBrandDialog({
  brand,
  open,
  isPending = false,
  submitError = null,
  onOpenChange,
  onConfirm,
}: DeactivateBrandDialogProps) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) setReason("");
  }, [open, brand]);

  function handleOpenChange(next: boolean) {
    if (!next) setReason("");
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Deactivate brand</DialogTitle>
          <DialogDescription>
            {brand
              ? `${brand.name} stays in this list so it can be reactivated. Public landing pages will 404.`
              : "Public landing pages will 404."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="deactivate-reason">Reason (optional)</Label>
          <Textarea
            id="deactivate-reason"
            placeholder="Optional reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        {submitError ? <p className="text-sm text-destructive">{submitError}</p> : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => onConfirm(reason.trim())}
            disabled={isPending}
          >
            {isPending ? "Deactivating..." : "Deactivate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
