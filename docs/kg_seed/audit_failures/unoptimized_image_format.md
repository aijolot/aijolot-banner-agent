---
title: "Hero images served as JPEG instead of WebP lose 25–35% file size and increase LCP"
kind: audit_failure
brand_id: null
metadata:
  category: perf
  evidence_source: "Lighthouse 'Serve images in next-gen formats'; Drive corpus — PNG screenshots 2026-05"
  applicable_when: "all banner sections serving product or background images"
---

The banner screenshots in the Drive corpus are PNG files (1.4–2.7MB), which is appropriate for screenshots but not for served images. Shopify's image CDN automatically serves WebP when the browser supports it — but only if the image_url filter is used correctly with an explicit width parameter. Without a width parameter, Shopify may serve the original format at original resolution. Lighthouse "Serve images in next-gen formats" audit reports potential file size savings. Remediation: always use `{{ image | image_url: width: W | image_tag }}` rather than `{{ image.src }}` directly. For multiple srcset sizes, use Shopify's responsive image helper with the sizes attribute.
