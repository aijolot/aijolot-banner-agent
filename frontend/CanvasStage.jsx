/* global React, Icon, GlassCard, Button, Badge, Avatar, Kicker, Spinner, Banner,
   ApprovalPanel, CommentsPanel, SEGMENTS, SEGMENT_ORDER, VARIANTS, COMMENTS_SEED, APPROVERS_SEED,
   ReviewApi, GenerationApi, CampaignApi, errorText, layoutCells, BannerLayout, UUID_RE, AIJOLOT_DEMO_IDS,
   isApiCampaign */
// Aijolot Banner Agent — Stage 3: collaborative canvas (Modules 4, 6, 7).
const { useState: useStateCV, useRef: useRefCV, useEffect: useEffectCV } = React;

const DEVICES = [
  { id: "desktop", icon: "monitor", w: "100%", label: "1440px" },
  { id: "tablet", icon: "tablet", w: 680, label: "768px" },
  { id: "mobile", icon: "smartphone", w: 360, label: "390px" },
];

let CID = 100;
const ACCENT_MAP = { cyan: "#28C7F0", gold: "#E7C76B", rose: "#F6B3CE" };

function backendReviewerStatus(status) {
  if (status === "changes_requested" || status === "rejected") return "changes";
  return status === "approved" ? "approved" : "pending";
}
function mapBackendApprovers(thread) {
  const reviewers = thread && Array.isArray(thread.reviewers) ? thread.reviewers : [];
  if (!reviewers.length) return null;
  return reviewers.map((r, i) => {
    const seed = APPROVERS_SEED[i % APPROVERS_SEED.length];
    return {
      ...seed,
      id: r.user_id || r.id || seed.id,
      backendReviewerId: r.id,
      name: r.user_id ? `Reviewer ${String(r.user_id).slice(0, 8)}` : seed.name,
      role: r.role_label || seed.role || "Reviewer backend",
      status: backendReviewerStatus(r.status),
      note: r.note || null,
      backend: true,
    };
  });
}
function mapBackendComments(thread) {
  const rows = thread && Array.isArray(thread.comments) ? thread.comments : [];
  if (!rows.length) return null;
  return rows.map((c) => ({
    id: c.id,
    x: Math.round(c.pin_x == null ? 50 : c.pin_x),
    y: Math.round(c.pin_y == null ? 50 : c.pin_y),
    author: c.author_id ? `Usuario ${String(c.author_id).slice(0, 8)}` : "Backend",
    initials: "BE",
    grad: "linear-gradient(135deg,#0891B2,#22D3EE)",
    text: c.body || "Comentario backend",
    resolved: !!c.resolved,
    time: c.created_at ? "backend" : "—",
    backend: true,
  }));
}
function revisionMappings(rev) {
  const lmap = {}, smap = {}, labels = {};
  const layoutRows = Array.isArray(rev && rev.layout_variants) ? rev.layout_variants : [];
  layoutRows.forEach((lv, i) => {
    const visibleKey = ["A", "B", "C"].includes(lv.key) ? lv.key : (VARIANTS[i] && VARIANTS[i].id);
    if (!visibleKey) return;
    lmap[visibleKey] = lv.id || lv.variant_id || lv.key;
    labels[visibleKey] = lv.name || lv.label || lv.key || visibleKey;
  });
  const rows = Array.isArray(rev && rev.variants) ? rev.variants : [];
  rows.forEach((v) => {
    const key = v.segment_key || v.segment || v.audience_key;
    if (key && SEGMENTS[key]) smap[key] = v.id;
  });
  return { lmap, smap, labels };
}

function CanvasStage({ campaign, tweaks, placement, art, onNotice, onPublish }) {
  const [variant, setVariant] = useStateCV("A");
  const [segId, setSegId] = useStateCV("masculino");
  const [variantKey, setVariantKey] = useStateCV(null);  // selected real banner_variant tag
  const [device, setDevice] = useStateCV("desktop");
  const [comments, setComments] = useStateCV(() => COMMENTS_SEED.map((c) => ({ ...c })));
  const [approvers, setApprovers] = useStateCV(() => APPROVERS_SEED.map((a) => ({ ...a })));
  const [commentMode, setCommentMode] = useStateCV(false);
  const [editingId, setEditingId] = useStateCV(null);
  const [applied, setApplied] = useStateCV({ brighter: false, ctaContrast: false });
  const [refining, setRefining] = useStateCV(false);
  const [refineMsg, setRefineMsg] = useStateCV("");
  const [refineInput, setRefineInput] = useStateCV("");
  const [published, setPublished] = useStateCV(false);
  const [scheduled, setScheduled] = useStateCV(false);
  const stageRef = useRefCV(null);
  // Backend revision/thread context resolved on mount (fail-closed if absent).
  const [revision, setRevision] = useStateCV(null);
  const [revisionList, setRevisionList] = useStateCV([]);
  const [revisionMode, setRevisionMode] = useStateCV("local");
  const [layoutVariantIds, setLayoutVariantIds] = useStateCV({}); // { A,B,C -> variant uuid }
  const [layoutVariantLabels, setLayoutVariantLabels] = useStateCV({});
  const [segmentVariantIds, setSegmentVariantIds] = useStateCV({}); // { segment_key -> variant uuid }
  const [threadId, setThreadId] = useStateCV(null);
  const [threadStatus, setThreadStatus] = useStateCV(null);
  const [approvalMode, setApprovalMode] = useStateCV("local");
  const [backendCampaignStatus, setBackendCampaignStatus] = useStateCV((campaign && campaign.status) || "draft");
  const [backendNotice, setBackendNotice] = useStateCV("Cargando revisiones/aprobaciones backend…");

  useEffectCV(() => {
    if (typeof GenerationApi === "undefined") return;
    let alive = true;
    (async () => {
      setRevision(null);
      setRevisionList([]);
      setRevisionMode("local");
      setLayoutVariantIds({});
      setLayoutVariantLabels({});
      setSegmentVariantIds({});
      setThreadId(null);
      setThreadStatus(null);
      setApprovalMode("local");
      setApprovers(APPROVERS_SEED.map((a) => ({ ...a, localPrototype: true })));
      setComments(COMMENTS_SEED.map((c) => ({ ...c, localPrototype: true })));
      setBackendCampaignStatus((campaign && campaign.status) || "draft");
      if (!campaign || !isApiCampaign || !isApiCampaign(campaign)) {
        setBackendNotice("Vista local/prototipo: variantes, comentarios y aprobaciones no están respaldados por backend.");
        return;
      }
      try {
        if (typeof CampaignApi !== "undefined" && CampaignApi.get) {
          try {
            const full = await CampaignApi.get(campaign.id);
            if (alive && full && full.status) setBackendCampaignStatus(full.status);
          } catch (e) {
            if (alive) onNotice && onNotice({ tone: "amber", text: "No pude refrescar estado de campaña backend: " + errorText(e) });
          }
        }
        const listResult = GenerationApi.revisions ? await GenerationApi.revisions(campaign) : await GenerationApi.latestRevision(campaign);
        if (!alive) return;
        const rows = Array.isArray(listResult.data) ? listResult.data : (listResult.data ? [listResult.data] : []);
        if (listResult.fallback || !rows.length) {
          setBackendNotice((listResult && listResult.reason) || "Sin revisiones backend; segmentos/variantes son previsualización local/prototipo.");
          onNotice && onNotice({ tone: "amber", text: (listResult && listResult.reason) || "Sin revisiones backend; lienzo en modo prototipo local." });
          return;
        }
        const latest = rows.reduce((a, b) => ((b.revision_number || 0) >= (a.revision_number || 0) ? b : a));
        setRevisionList(rows);
        setRevision(latest);
        setRevisionMode("backend");
        const maps = revisionMappings(latest);
        setLayoutVariantIds(maps.lmap);
        setLayoutVariantLabels(maps.labels);
        setSegmentVariantIds(maps.smap);
        if (Object.keys(maps.lmap).length && !maps.lmap[variant]) setVariant(Object.keys(maps.lmap)[0]);
        setBackendNotice(`Revisión backend #${latest.revision_number || rows.length} cargada${rows.length > 1 ? ` (${rows.length} revisiones)` : ""}.`);

        const th = await ReviewApi.ensureThread(campaign, latest.id);
        if (!alive) return;
        if (!th.fallback && th.data) {
          const thread = th.data.thread || th.data.approval_thread || th.data;
          setThreadId(thread.id || thread.thread_id);
          setThreadStatus(thread.status || null);
          setApprovalMode("backend");
          const backendApprovers = mapBackendApprovers(thread);
          const backendComments = mapBackendComments(thread);
          if (backendApprovers) setApprovers(backendApprovers);
          if (backendComments) setComments(backendComments);
          onNotice && onNotice({ tone: "green", text: "Hilo de aprobación backend cargado" });
        } else {
          setApprovalMode("local");
          onNotice && onNotice({ tone: "amber", text: (th && th.reason) || "Aprobaciones locales/prototipo: backend no creó/cargó el hilo." });
        }
      } catch (e) {
        if (alive) {
          const msg = "Lienzo en modo local/prototipo: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || "error"));
          setBackendNotice(msg);
          onNotice && onNotice({ tone: "amber", text: msg });
        }
      }
    })();
    return () => { alive = false; };
  }, [campaign && campaign.id]);

  const seg = SEGMENTS[segId];
  // Real banner data from the persisted backend revision: concept copy, the
  // generated image, and the attached AI background. Null → demo fallback.
  const liveConcept = revisionMode === "backend" && revision && revision.concept ? revision.concept : null;
  const liveCopy = (liveConcept && liveConcept.copy) || {};
  const liveGenArt = (liveConcept && liveConcept.generated_art) || [];
  const liveLastArt = liveGenArt.length ? liveGenArt[liveGenArt.length - 1] : null;
  const liveBgObj = liveConcept && liveConcept.background;
  // Real personalization variants (one banner_variant per tag). Each has its own
  // copy; the shared layers (background + image) come from the concept.
  const realVariants = liveConcept && Array.isArray(revision.variants) ? revision.variants : [];
  const selectedVariant = realVariants.find((v) => v.segment_key === variantKey) || realVariants[0] || null;
  const variantCopy = selectedVariant || {};
  // Per-variant featured product image (when the variant chose its own product),
  // else the shared generated art. So switching Hombre/Mujer swaps the perfume photo.
  const variantProduct = (selectedVariant && selectedVariant.audience_rule && selectedVariant.audience_rule.featured_product) || {};
  const live = liveConcept ? {
    eyebrow: String((selectedVariant ? variantCopy.eyebrow : null) || liveCopy.eyebrow || liveCopy.audience || "").toUpperCase().slice(0, 40) || null,
    headline: (selectedVariant ? variantCopy.headline : null) || liveCopy.headline || null,
    sub: (selectedVariant ? variantCopy.subheadline : null) || liveCopy.subheadline || null,
    cta: (selectedVariant ? variantCopy.cta_text : null) || liveCopy.cta || null,
    promo: (selectedVariant ? variantCopy.cta_text : null) || liveCopy.cta || null,
    brandName: "",
    imageUrl: variantProduct.product_image_url || (liveLastArt && liveLastArt.public_url) || null,
    bgCss: (liveBgObj && liveBgObj.css) || null,
  } : null;
  const approvedCount = approvers.filter((a) => a.status === "approved").length;
  const allApproved = approvedCount === approvers.length;
  const missing = approvers.length - approvedCount;
  const dev = DEVICES.find((d) => d.id === device);
  const gridLayout = (placement && placement.layout) || { cols: [{ rows: 1, w: 1 }] };
  const cellCount = layoutCells(gridLayout);
  const locked = tweaks.lockLayout && tweaks.lockLayout !== "auto";
  const layoutVariant = locked ? tweaks.lockLayout : variant;
  const bannerAccent = tweaks.bannerAccent && tweaks.bannerAccent !== "auto" ? ACCENT_MAP[tweaks.bannerAccent] : undefined;
  const apiCampaign = !!(campaign && UUID_RE.test(campaign.id || ""));
  const backendApproved = approvalMode === "backend" && (threadStatus === "approved" || backendCampaignStatus === "approved" || backendCampaignStatus === "scheduled");
  const backendSchedulableStatus = ["approved", "scheduled"].includes(backendCampaignStatus) || threadStatus === "approved";
  const backendScheduleReady = apiCampaign && revision && revision.id && backendApproved && backendSchedulableStatus;
  const backendPublishReady = apiCampaign && revision && revision.id && backendCampaignStatus === "scheduled";
  const scheduleGuardReason = !apiCampaign
    ? "Programación backend no disponible: la campaña local/prototipo no tiene UUID."
    : !revision
      ? "Programación bloqueada: no hay revisión backend seleccionada. Genera/carga una revisión primero."
      : approvalMode !== "backend"
        ? "Programación bloqueada: las aprobaciones son locales/prototipo; backend no confirmó el hilo."
        : !backendApproved
          ? "Programación bloqueada: backend no reporta aprobación real de la revisión."
          : !backendSchedulableStatus
            ? `Programación bloqueada: estado backend actual '${backendCampaignStatus || "desconocido"}' no es approved/scheduled.`
            : "";
  const publishGuardReason = !apiCampaign
    ? "Publicación fail-closed: la campaña local/prototipo no tiene UUID backend."
    : !revision
      ? "Publicación fail-closed: no hay revisión backend seleccionada."
      : backendCampaignStatus !== "scheduled"
        ? `Publicación fail-closed: backend requiere campaña scheduled; estado actual '${backendCampaignStatus || "desconocido"}'.`
        : "";

  async function setApprover(id, status) {
    setApprovers((arr) => arr.map((a) => a.id === id ? { ...a, status, note: status === "approved" ? "Aprobado." : "Solicita ajustes." } : a));
    try {
      const r = status === "approved"
        ? await ReviewApi.approve(threadId)
        : await ReviewApi.requestChangesThread(threadId, "Solicita ajustes.");
      if (r.fallback) {
        onNotice && onNotice({ tone: "amber", text: `Aprobaciones locales/prototipo: ${r.reason}` });
      } else {
        const thread = r.data && (r.data.thread || r.data.approval_thread || r.data);
        if (thread && thread.status) setThreadStatus(thread.status);
        onNotice && onNotice({ tone: "green", text: status === "approved" ? "Aprobación registrada en backend" : "Cambios solicitados en backend" });
      }
    } catch (e) {
      onNotice && onNotice({ tone: "amber", text: "Backend no registró la acción de aprobación; cambio solo local/prototipo: " + errorText(e) });
    }
  }
  // Backend variant selection: local tab switch always happens; if a real
  // variant uuid resolves, persist the choice. Fail-closed otherwise.
  async function selectLayoutVariant(key) {
    setVariant(key);
    const variantId = layoutVariantIds[key];
    if (!variantId) {
      if (revisionMode !== "backend") onNotice && onNotice({ tone: "amber", text: "Variante local/prototipo: no hay revisión backend para persistir esta selección." });
      return;
    }
    const r = await GenerationApi.selectVariant(campaign, variantId);
    onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: `Variante ${key} seleccionada en backend` });
  }
  async function selectSegment(id) {
    setSegId(id);
    const variantId = segmentVariantIds[id];
    if (!variantId) {
      if (revisionMode !== "backend") onNotice && onNotice({ tone: "amber", text: "Segmento local/prototipo: no hay variante backend para persistir esta selección." });
      return;
    }
    const r = await GenerationApi.selectVariant(campaign, variantId);
    onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: `Segmento ${id} seleccionado en backend` });
  }
  async function resolveComment(id) {
    setComments((arr) => arr.map((c) => c.id === id ? { ...c, resolved: true } : c));
    if (UUID_RE.test(id || "")) {
      const r = await ReviewApi.resolveCommentSafe(id, { resolved_by: AIJOLOT_DEMO_IDS.user });
      if (r.fallback) onNotice && onNotice({ tone: "amber", text: r.reason });
      else onNotice && onNotice({ tone: "green", text: "Comentario resuelto en backend" });
    } else {
      onNotice && onNotice({ tone: "amber", text: "Comentario resuelto solo local/prototipo; no tiene id backend." });
    }
  }

  function addComment(e) {
    if (!commentMode || !stageRef.current) return;
    const r = stageRef.current.getBoundingClientRect();
    const x = Math.round(((e.clientX - r.left) / r.width) * 100);
    const y = Math.round(((e.clientY - r.top) / r.height) * 100);
    const id = "c" + (CID++);
    setComments((arr) => [...arr, { id, x, y, author: "Mara Voss", initials: "MV", grad: "linear-gradient(135deg,#F72585,#8B5CF6)", text: "", resolved: false, time: "ahora", _new: true }]);
    setEditingId(id);
    setCommentMode(false);
  }
  async function saveDraft(id, text) {
    const pin = comments.find((c) => c.id === id);
    setComments((arr) => arr.map((c) => c.id === id ? { ...c, text, _new: false } : c));
    setEditingId(null);
    const r = await ReviewApi.addComment(threadId, {
      author_id: AIJOLOT_DEMO_IDS.user,
      body: text,
      pin_x: pin ? pin.x : null,
      pin_y: pin ? pin.y : null,
      banner_variant_id: segmentVariantIds[segId] || null,
      layout_variant_key: layoutVariant,
      device_key: device,
    });
    if (r.fallback) onNotice && onNotice({ tone: "amber", text: `Comentario local/prototipo: ${r.reason}` });
    else {
      onNotice && onNotice({ tone: "green", text: "Comentario guardado en backend" });
      if (r.data && r.data.id) setComments((arr) => arr.map((c) => c.id === id ? { ...c, id: r.data.id } : c));
    }
  }
  function cancelDraft(id) {
    setComments((arr) => arr.filter((c) => !(c.id === id && c._new)));
    setEditingId(null);
  }

  function refine(text) {
    if (refining) return;
    const t = text.toLowerCase();
    setRefining(true);
    setRefineInput("");
    // Scoped, non-destructive edit: the backend classifies the target
    // (text/background/image) and returns a NEW revision; the canvas Banner
    // re-renders from revision.concept. A light local shim keeps it responsive.
    const backend = GenerationApi.bannerEdit(campaign, text, null, revision && revision.id)
      .catch((e) => ({ ok: true, fallback: true, reason: "Backend no aceptó la edición (" + (typeof errorText !== "undefined" ? errorText(e) : (e.message || "error")) + ").", data: null }));
    setTimeout(async () => {
      const next = { ...applied };
      if (/bril|luz|clar|ilumin/.test(t)) next.brighter = true;
      if (/bot|cta|contrast|resalt/.test(t)) next.ctaContrast = true;
      if (/oscur|sobrio/.test(t)) next.brighter = false;
      setApplied(next);
      setComments((arr) => arr.map((c) => {
        const ct = c.text.toLowerCase();
        if (!c.resolved && ((/bril|luz/.test(t) && /bril|luz/.test(ct)) || (/bot|cta|contrast|resalt/.test(t) && /bot|cta|contrast|resalt/.test(ct)))) return { ...c, resolved: true };
        return c;
      }));
      const r = await backend;
      let run = r && r.data && r.data.generation_run;
      let editedRevision = r && r.data && r.data.revision;
      const targets = (run && run.metadata && run.metadata.edit_targets) || [];
      if (r && !r.fallback && run) {
        const TERMINAL = ["succeeded", "failed", "escalated"];
        // Async job: poll the run until it finishes (the edit runs in the
        // background; image edits can take ~10-20s), then load the new revision.
        for (let attempt = 0; attempt < 30 && !TERMINAL.includes(run.status); attempt += 1) {
          await new Promise((res) => setTimeout(res, 1500));
          try { run = (await GenerationApi.get(run.id)) || run; } catch (_e) { break; }
        }
        if (run.status === "succeeded") {
          const rev = await GenerationApi.latestRevision(campaign);
          if (rev && !rev.fallback && rev.data) editedRevision = rev.data;
          if (editedRevision) setRevision(editedRevision);
          const label = targets.length ? targets.join(", ") : "banner";
          setRefineMsg(`Editado (${label}) · revisión #${editedRevision ? editedRevision.revision_number : "?"}`);
          onNotice && onNotice({ tone: "green", text: `Edición aplicada en backend (${label}); el resto se preservó.` });
        } else {
          setRefineMsg("La edición no terminó.");
          onNotice && onNotice({ tone: "amber", text: (run && run.error_message) || "El backend no confirmó la edición." });
        }
      } else {
        setRefineMsg("Ajuste local (sin backend).");
        onNotice && onNotice({ tone: "amber", text: (r && r.reason) || "Edición aplicada solo localmente." });
      }
      setRefining(false);
    }, 1200);
  }

  async function publish() {
    setPublished(false);
    if (!backendPublishReady) {
      onNotice && onNotice({ tone: "amber", text: publishGuardReason || "Publicación fail-closed: backend aún no acepta publicar." });
      return;
    }
    let canAdvance = false;
    try {
      const r = await ReviewApi.publish(campaign);
      if (r.fallback) {
        onNotice && onNotice({ tone: "amber", text: `Publicación fail-closed: ${r.reason}` });
      } else {
        onNotice && onNotice({ tone: "green", text: "Publicación aceptada por backend" });
        canAdvance = true;
      }
    } catch (e) {
      const code = e.status ? `HTTP ${e.status}: ` : "";
      onNotice && onNotice({ tone: "amber", text: "Publicación fail-closed: " + code + errorText(e) });
    }
    if (canAdvance) { setScheduled(false); setPublished(true); setTimeout(() => onPublish && onPublish(), 950); }
  }
  async function schedule(s) {
    setScheduled(false);
    if (!backendScheduleReady) {
      onNotice && onNotice({ tone: "amber", text: scheduleGuardReason || "Programación bloqueada por guardrails backend." });
      return;
    }
    let accepted = false;
    try {
      const r = await ReviewApi.schedule(campaign, s);
      if (r.fallback) {
        onNotice && onNotice({ tone: "amber", text: `Programación rechazada/fail-closed: ${r.reason}` });
      } else {
        onNotice && onNotice({ tone: "green", text: "Agenda guardada en backend" });
        setBackendCampaignStatus("scheduled");
        accepted = true;
      }
    } catch (e) {
      const code = e.status ? `HTTP ${e.status}: ` : "";
      onNotice && onNotice({ tone: "amber", text: "Programación rechazada por backend: " + code + errorText(e) });
    }
    if (accepted) setScheduled(true);
  }

  const visibleVariantKeys = Object.keys(layoutVariantIds).length ? Object.keys(layoutVariantIds) : VARIANTS.map((v) => v.id);
  const visibleVariants = VARIANTS.filter((v) => visibleVariantKeys.includes(v.id));
  const currentVariantMeta = VARIANTS.find((v) => v.id === layoutVariant) || VARIANTS[0];

  const TabBtn = ({ active, onClick, children, title }) => (
    <button onClick={onClick} title={title} style={{
      display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 12.5, fontWeight: 600,
      padding: "7px 12px", borderRadius: 9, cursor: "pointer", whiteSpace: "nowrap",
      border: `1px solid ${active ? "rgba(34,211,238,.5)" : "transparent"}`,
      background: active ? "rgba(34,211,238,.14)" : "transparent", color: active ? "#0891B2" : "#68737D",
      transition: "background .15s",
    }}>{children}</button>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 5 de 6 · Lienzo colaborativo</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Revisa, comenta y aprueba</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <Badge tone={revisionMode === "backend" ? "cyan" : "amber"} icon={revisionMode === "backend" ? "git-branch" : "flask-conical"}>
            {revisionMode === "backend" ? `${visibleVariants.length} variantes backend · ${revisionList.length} revisiones` : "Vista local/prototipo"}
          </Badge>
          <Badge tone={approvalMode === "backend" ? "green" : "amber"} icon={approvalMode === "backend" ? "shield-check" : "triangle-alert"}>
            {approvalMode === "backend" ? `Aprobación backend · ${threadStatus || "abierta"}` : "Aprobaciones locales/prototipo"}
          </Badge>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.7fr) minmax(300px,1fr)", gap: 16, alignItems: "start" }}>
        {/* MAIN */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* toolbar */}
          <GlassCard style={{ padding: 10, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 2, background: "rgba(248,250,252,0.8)", borderRadius: 11, padding: 3 }}>
              {visibleVariants.map((v) => (
                <TabBtn key={v.id} active={layoutVariant === v.id} onClick={() => !locked && selectLayoutVariant(v.id)} title={locked ? "Layout fijado en Tweaks" : (layoutVariantIds[v.id] ? `Backend ${layoutVariantIds[v.id]}` : "Variante local/prototipo") }>
                  {layoutVariantLabels[v.id] || (v.id === "A" ? "Spotlight" : v.id === "B" ? "Split" : "Minimal")}
                  {layoutVariantIds[v.id] && <Icon name="database" size={12} />}
                  {v.recommended && layoutVariant === v.id && <Icon name="sparkles" size={12} />}
                </TabBtn>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", gap: 2, background: "rgba(248,250,252,0.8)", borderRadius: 11, padding: 3 }}>
              {DEVICES.map((d) => (
                <TabBtn key={d.id} active={device === d.id} onClick={() => setDevice(d.id)} title={d.label}><Icon name={d.icon} size={15} /></TabBtn>
              ))}
            </div>
          </GlassCard>

          {/* banner stage */}
          <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
            background: "rgba(255,255,255,0.55)",
            backgroundImage: "radial-gradient(rgba(148,163,184,.18) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, alignSelf: "stretch", justifyContent: "center", fontFamily: "Space Grotesk", fontSize: 11, color: "#94A3B8" }}>
              <Icon name={dev.icon} size={13} /> {dev.label} · {currentVariantMeta.name}{placement ? ` · ${placement.name}` : ""}{cellCount > 1 ? ` · ${gridLayout.cols.length} col / ${cellCount} celdas` : ""}{art ? ` · ${art.fold}% sobre el pliegue` : ""} · {revisionMode === "backend" ? "revisión backend" : "preview local/prototipo"}
            </div>
            <div style={{ width: dev.w, maxWidth: "100%", transition: "width .35s ease" }}>
              <div ref={stageRef} onClick={addComment} style={{ position: "relative", cursor: commentMode ? "crosshair" : "default" }}>
                {cellCount > 1 ? (
                  <BannerLayout layout={gridLayout} gap={12} cell={(i) => (
                    <Banner key={i} seg={seg} variant={layoutVariant} slot={i === 0} font={tweaks.bannerFont} accent={bannerAccent}
                      brighter={applied.brighter} ctaContrast={applied.ctaContrast} idSuffix={"-cv" + i} live={live} />
                  )} />
                ) : (
                  <Banner seg={seg} variant={layoutVariant} slot font={tweaks.bannerFont} accent={bannerAccent}
                    brighter={applied.brighter} ctaContrast={applied.ctaContrast} idSuffix={"-cv"} live={live} />
                )}

                {/* refine shimmer overlay */}
                {refining && (
                  <div style={{ position: "absolute", inset: 0, borderRadius: 18, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(10,20,32,.35)", backdropFilter: "blur(2px)", zIndex: 20 }}>
                    <div style={{ position: "absolute", inset: 0, background: "linear-gradient(100deg,transparent 30%,rgba(40,199,240,.25) 50%,transparent 70%)", backgroundSize: "500px 100%", animation: "shimmer 1.2s linear infinite" }} />
                    <div style={{ display: "flex", alignItems: "center", gap: 9, background: "rgba(255,255,255,.92)", borderRadius: 9999, padding: "9px 16px", zIndex: 2 }}>
                      <Spinner size={15} /><span style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#0891B2" }}>El agente está refinando…</span>
                    </div>
                  </div>
                )}

                {/* comment pins */}
                {comments.map((c, i) => (
                  <div key={c.id} title={c.text} style={{ position: "absolute", left: `${c.x}%`, top: `${c.y}%`, transform: "translate(-50%,-50%)", zIndex: 15 }}>
                    <div style={{ position: "relative", width: 26, height: 26, borderRadius: "50% 50% 50% 2px", background: c.resolved ? "#94A3B8" : "#fff", border: `2px solid ${c.resolved ? "#CBD5E1" : "#22D3EE"}`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 6px 14px rgba(15,23,42,.25)", cursor: "pointer" }}>
                      <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 12, color: c.resolved ? "#fff" : "#0891B2" }}>{i + 1}</span>
                      {c.id === editingId && <span style={{ position: "absolute", inset: -6, borderRadius: "50%", border: "2px solid #22D3EE", animation: "ringGrow 1.4s ease-out infinite" }} />}
                    </div>
                  </div>
                ))}
                {commentMode && (
                  <div style={{ position: "absolute", top: 10, left: "50%", transform: "translateX(-50%)", zIndex: 16, background: "rgba(0,43,87,.9)", color: "#fff", fontFamily: "Inter", fontSize: 11.5, padding: "5px 12px", borderRadius: 9999 }}>
                    Toca el banner para anclar un comentario
                  </div>
                )}
              </div>
            </div>
          </GlassCard>

          {/* segment personalization */}
          <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="users-round" size={15} color="#0891B2" />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>Hiper-personalización · Customer Tags</span>
              <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8", marginLeft: "auto" }}>{selectedVariant ? (selectedVariant.audience_rule && selectedVariant.audience_rule.audience) || selectedVariant.segment_label : seg.audience}</span>
            </div>
            {realVariants.length ? (
              <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(realVariants.length, 3)},1fr)`, gap: 10 }}>
                {realVariants.map((v) => {
                  const on = (variantKey || (realVariants[0] && realVariants[0].segment_key)) === v.segment_key;
                  return (
                    <button key={v.id || v.segment_key} onClick={() => setVariantKey(v.segment_key)} style={{
                      display: "flex", flexDirection: "column", gap: 3, padding: "11px 13px", borderRadius: 12, cursor: "pointer", textAlign: "left",
                      border: `1.5px solid ${on ? "#22D3EE" : "#EEF2F6"}`, background: on ? "rgba(34,211,238,.08)" : "rgba(248,250,252,0.7)", transition: "all .15s",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Icon name="user-round" size={14} color={on ? "#0891B2" : "#94A3B8"} />
                        <span style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{v.segment_label || v.segment_key}</span>
                      </div>
                      <span style={{ fontFamily: "Space Grotesk", fontSize: 9.5, color: "#94A3B8" }}>{v.customer_tag || v.segment_key}</span>
                      <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#64748B", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{v.headline || "—"}</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
                {SEGMENT_ORDER.map((id) => {
                  const s = SEGMENTS[id]; const on = segId === id;
                  return (
                    <button key={id} onClick={() => selectSegment(id)} style={{
                      display: "flex", alignItems: "center", gap: 10, padding: "11px 13px", borderRadius: 12, cursor: "pointer", textAlign: "left",
                      border: `1.5px solid ${on ? "#22D3EE" : "#EEF2F6"}`, background: on ? "rgba(34,211,238,.08)" : "rgba(248,250,252,0.7)", transition: "all .15s",
                    }}>
                      <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0, background: `linear-gradient(150deg,${s.palette.bgB},${s.palette.bgA})`, display: "flex", alignItems: "center", justifyContent: "center", color: s.palette.cap }}>
                        <Icon name={s.icon} size={15} />
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{s.label.split(": ")[1] || s.label}</div>
                        <div style={{ fontFamily: "Space Grotesk", fontSize: 10, color: "#94A3B8" }}>{s.tag}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
            <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#68737D", display: "flex", alignItems: "center", gap: 6 }}>
              <Icon name={revisionMode === "backend" ? "database" : "info"} size={12} color="#94A3B8" /> {backendNotice}
            </div>
            <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#68737D", display: "flex", alignItems: "center", gap: 6 }}>
              <Icon name="info" size={12} color="#94A3B8" /> Una sola campaña, variantes invisibles que el agente sirve según el tag del cliente.
            </div>
          </GlassCard>

          {/* refinement loop */}
          <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 11 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 28, height: 28, borderRadius: 9, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}><Icon name="wand-sparkles" size={15} /></div>
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>Refinar con el agente</span>
              {refineMsg && !refining && <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 11.5, color: "#16A34A", fontWeight: 500 }}><Icon name="check" size={13} /> {refineMsg}</span>}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", background: "rgba(241,245,249,0.6)", border: "1px solid #E2E8F0", borderRadius: 12, padding: 7 }}>
              <input value={refineInput} onChange={(e) => setRefineInput(e.target.value)} disabled={refining}
                onKeyDown={(e) => { if (e.key === "Enter" && refineInput.trim()) refine(refineInput); }}
                placeholder="Ej: haz el fondo más brillante, cambia el tono del botón…"
                style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "Inter", fontSize: 13, color: "#002B57", padding: "6px 8px" }} />
              <Button variant="default" icon="send" onClick={() => refineInput.trim() && refine(refineInput)} disabled={refining || !refineInput.trim()} style={{ padding: "9px 13px" }} />
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["Haz el fondo más brillante", "Botón en color contraste"].map((s) => (
                <button key={s} onClick={() => refine(s)} disabled={refining} style={{ fontFamily: "Inter", fontSize: 11.5, padding: "6px 12px", borderRadius: 9999, border: "1px solid #E2E8F0", background: "#fff", color: "#0891B2", cursor: refining ? "default" : "pointer" }}>+ {s}</button>
              ))}
            </div>
          </GlassCard>
        </div>

        {/* RIGHT */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <ApprovalPanel approvers={approvers} onSet={setApprover} published={published} mode={approvalMode} threadStatus={threadStatus} />
          <PublishPanel allApproved={allApproved} missing={missing} published={published} scheduled={scheduled}
            backendScheduleReady={!!backendScheduleReady} backendPublishReady={!!backendPublishReady}
            guardrailReason={backendPublishReady ? "" : (publishGuardReason || scheduleGuardReason)} scheduleGuardReason={scheduleGuardReason}
            publishGuardReason={publishGuardReason} approvalMode={approvalMode} backendStatus={backendCampaignStatus}
            onPublishNow={publish} onSchedule={schedule} onEditSchedule={() => setScheduled(false)} onView={() => onPublish && onPublish()} />
          <CommentsPanel comments={comments} onResolve={resolveComment} commentMode={commentMode} setCommentMode={setCommentMode}
            editingId={editingId} onSaveDraft={saveDraft} onCancelDraft={cancelDraft} />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CanvasStage });
