## Problem

`wait_for_profile_photo_ready` returned `True` as soon as the topcard container `div[aria-label="Profile photo"]` appeared in the DOM. React renders the container shell before populating the inner `figure > img`, so the photo extractor ran too early and always found 0 images — producing a completed job with an empty dossier.

Debug log confirmed the race:

```
topcard container='div[aria-label="Profile photo"]' count=1 figure_count=0
topcard container='div[aria-label="Profile photo"]' count=1 img_count=0 attrs={}
```

## Fix

- Wait condition now checks for `div[aria-label="Profile photo"] figure img` (fully-rendered state) instead of just the container shell.
- Selector confirmed unique via browser console: `document.querySelectorAll('figure img').length` = 26; scoped selector = 1.
- Also adds `ARIA_FIGURE_PHOTO_SELECTOR` to `DOM_PHOTO_SELECTORS` as a high-priority extraction fallback.

## Files changed

- `backend/app/integrations/linkedin/constants.py` — new `ARIA_FIGURE_PHOTO_SELECTOR`, added to `DOM_PHOTO_SELECTORS`
- `backend/app/integrations/linkedin/photo.py` — tightened wait condition; imports new constant
