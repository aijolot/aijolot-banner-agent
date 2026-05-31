# Image prompt refine (image-prompt-refine skill)

Model: `gemini-3.1-pro` · Output: plain string

Given a `Concept.image_prompt` and `BrandContext.image_style_directives`, produce a final image prompt safe for Nano Banana Pro (`gemini-3.1-pro-image`).

**Strip / forbid:**
- Any text or logos
- Any reference to UI elements (buttons, modals, screens)
- Faces of specific real people; full visible faces of generic people (use back, profile, or out-of-frame composition instead)
- Brand names other than the current `BrandContext.name`

**Enforce:**
- Aspect 16:9 implied
- Lighting + mood from `image_style_directives`
- Palette consistent with `BrandContext.palette.primary/accent`
- Photographic realism unless the brand directive says otherwise

Output: a single paragraph prompt, 60-120 words, ready for image gen.
